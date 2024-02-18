#!/usr/bin/python3
# commande pour le dump : docker exec -t ubuntu-database-1 pg_dump -U teslamate teslamate > teslamate-$(date +'%m-%d-%Y')

import os
import configparser
from datetime import datetime
from minio import Minio
import tarfile


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

def upload_file_to_minio(minioClient, bucket_name, dst_file, file_path):
    # Envoyer le fichier vers MinIO
    try:
        with open(file_path, 'rb') as file_data:
            file_stat = os.stat(file_path)
            minioClient.put_object(bucket_name, dst_file, file_data, file_stat.st_size)
    except Exception as e:
        print(f"Une erreur s'est produite lors de l'envoi du fichier vers MinIO : {e}")

def make_tarfile(output_filename, source_dir):
    try:
        with tarfile.open(output_filename, 'w:gz') as tar:
            tar.add(source_dir, arcname=os.path.basename(source_dir))
    except Exception as e:
        print(f"Une erreur s'est produite lors de la création de l'archive tar : {e}")

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

current_date = datetime.now().strftime('%Y-%m-%d')
backup_file = "teslamate{0}".format(current_date)
os.system("docker exec -t ubuntu-database-1 pg_dump -U teslamate teslamate > {0}".format(backup_file))

# Envoyer le fichier vers MinIO
storage_url, access_key, secret_key = load_minio_credentials()
minioClient = Minio(storage_url,
        access_key=access_key,
        secret_key=secret_key,
        secure=True)

bucket_name = "teslamate"

output_file = f"teslamate-{datetime.now().strftime('%m-%d-%Y')}.tar.gz"
make_tarfile(output_file, backup_file)

destination = output_file.removeprefix("/tmp/")
upload_file_to_minio(minioClient, bucket_name, destination, output_file)
keep_last_n_files(minioClient, bucket_name)

# clean
if os.path.isfile(output_file):
    os.remove(output_file)
    print(f"Le fichier {output_file} a été supprimé.")
else:
    print(f"Le fichier {output_file} n'existe pas.")

if os.path.isfile(backup_file):
    os.remove(backup_file)
    print(f"Le fichier {backup_file} a été supprimé.")
else:
    print(f"Le fichier {backup_file} n'existe pas.")
