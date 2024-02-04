#!/usr/bin/python3

import docker

import tarfile
import os
from datetime import datetime

import sys

from minio import Minio
from minio.deleteobjects import DeleteObject
import configparser



if len(sys.argv) != 2:
    print("Le script prend un argument : le nom du conteneur.")
    sys.exit(1)

name = sys.argv[1]


client = docker.from_env()
containers = client.containers.list(all=True)

def load_minio_credentials(file_path="/etc/minio/credz.conf"):
    config = configparser.ConfigParser()

    try:
        config.read(file_path)
        storage_url = config.get("minio", "storage_url")
        access_key = config.get("minio", "access_key")
        secret_key = config.get("minio", "secret_key")

        return storage_url, access_key, secret_key
    except Exception as e:
        print(f"Erreur lors de la lecture du fichier de configuration {file_path}: {e}")
        return None, None

def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, 'w:gz') as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))

def upload_file_to_minio(minioClient, bucket_name, dst_file, file_path):
    # Envoyer le fichier vers MinIO
    with open(file_path, 'rb') as file_data:
        file_stat = os.stat(file_path)
        minioClient.put_object(bucket_name, dst_file, file_data, file_stat.st_size)

def keep_last_n_files(minioClient, bucket_name):
    object_info_list = []
    objects = minioClient.list_objects(bucket_name, recursive=True)

    for obj in objects:
        object_info_list.append({
            "name": obj.object_name,
            "last_modified": obj.last_modified
        })
        object_info_list.sort(key=lambda x: x["last_modified"], reverse=True)
        objects_to_keep = object_info_list[:7]
        for obj in object_info_list:
            if obj not in objects_to_keep:
                minioClient.remove_object(bucket_name, obj["name"])
                print(f"Objet {obj['name']} supprimé.")

for container in containers:
    if container.name == name:
        container.stop()
        container_info = container.attrs
        mounts = container_info['Mounts']
        for mount in mounts:
            path = mount['Source']

            current_date = datetime.now().strftime('%Y-%m-%d')
            output_file = f'/tmp/{container.name}_{current_date}.tar.gz'
            make_tarfile(output_file, path)
            container.start()
            print(f"Le contenu de {path} a été compressé dans {output_file}.")

            storage_url, access_key, secret_key = load_minio_credentials()
            minioClient = Minio(storage_url,
                    access_key=access_key,
                    secret_key=secret_key,
                    secure=True)

            bucket_name = name

            destination = output_file.removeprefix("/tmp/")
            upload_file_to_minio(minioClient, bucket_name, destination, output_file)
            keep_last_n_files(minioClient, bucket_name)

            if os.path.isfile(output_file):
                os.remove(output_file)
                print(f"Le fichier {output_file} a été supprimé.")
            else:
                print(f"Le fichier {output_file} n'existe pas.")

