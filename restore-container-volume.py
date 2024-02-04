#!/usr/bin/python3

import docker

import tarfile
import os
import shutil
from datetime import datetime

import sys
import configparser

from minio import Minio


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

def download_latest_file(minio_client, bucket_name, destination_folder):

    objects = minio_client.list_objects(bucket_name, recursive=True)
    sorted_objects = sorted(objects, key=lambda obj: obj.last_modified, reverse=True)

    if not sorted_objects:
        print("Le bucket est vide.")
        return

    latest_object = sorted_objects[0]
    object_name = latest_object.object_name
    destination_path = f"{destination_folder}/{object_name}"

    print(f"Téléchargement du fichier le plus récent : {object_name} ...")
    minio_client.fget_object(bucket_name, object_name, destination_path)

    print(f"Le fichier a été téléchargé avec succès vers : {destination_path}")
    return destination_path

def clear_data_folder(folder):

    try:
        shutil.rmtree(folder)
        os.makedirs(folder)

        print(f"Le contenu du dossier {folder} a été effacé avec succès.")
    except Exception as e:
        print(f"Erreur lors de la suppression du contenu du dossier {folder}: {e}")

def change_owner_and_group(directory_path):
    try:
        os.chown(directory_path, "www-data", "www-data")

        print(f"Le propriétaire et le groupe du répertoire {directory_path} ont été modifiés avec succès.")
    except Exception as e:
        print(f"Erreur lors de la modification du propriétaire et du groupe du répertoire {directory_path}: {e}")

def extract_tar_gz(tar_gz_file, destination_folder):
    try:
        # Ouvrir le fichier .tar.gz en mode lecture
        with tarfile.open(tar_gz_file, 'r:gz') as tar:
            # Extraire tous les fichiers dans le répertoire spécifié
            tar.extractall(path=destination_folder)

        print(f"Le fichier {tar_gz_file} a été décompressé avec succès dans {destination_folder}.")
    except Exception as e:
        print(f"Erreur lors de la décompression de {tar_gz_file}: {e}")


for container in containers:
    if container.name == name:
        storage_url, access_key, secret_key = load_minio_credentials()
        minioClient = Minio(storage_url,
                access_key=access_key,
                secret_key=secret_key,
                secure=True)

        bucket_name = name
        destination_folder = "/tmp"
        latest_backup = download_latest_file(minioClient, bucket_name, destination_folder)

        container.stop()
        container_info = container.attrs
        mounts = container_info['Mounts']
        for mount in mounts:
            path = mount['Source']

        clear_data_folder(path)

        extract_tar_gz(latest_backup, path.rstrip("_data"))
        container.start()


