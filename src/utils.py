import os
import uuid
import gzip
import hashlib


def generate_random_id() -> str:
    return uuid.uuid4()


def gzip_files(folder_path: str, output_path: str) -> None:

    if not folder_path or not os.path.isdir(folder_path):
        return

    file_names = os.listdir(folder_path)

    if not os.path.isdir(output_path):
        os.mkdir(output_path)

    for file_name in file_names:
        with open(f"{folder_path}/{file_name}", "rb") as f_in, gzip.open(f"{output_path}/{file_name}.gz", "wb") as f_out:
            f_out.writelines(f_in)


def get_SHA256_hash(file_path: str):

    sha256 = hashlib.sha256()

    with open(file_path, "rb") as f:
        data = f.read()
        sha256.update(data)

    hash = sha256.hexdigest()

    print(
        f"[firebase-hosting] SHA256 hash for {file_path} is {hash}", end="\n\n\n",
    )

    return hash
