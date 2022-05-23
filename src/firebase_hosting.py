from oauth2client.service_account import ServiceAccountCredentials
import requests
import json


class FirebaseHosting:
    def __init__(self):
        pass

    def get_access_token(self, credentials_path: str) -> str:
        SCOPES = ["https://www.googleapis.com/auth/firebase.hosting"]

        credentials = ServiceAccountCredentials.from_json_keyfile_name(
            credentials_path,
            SCOPES,
        )

        access_token_info = credentials.get_access_token()
        return access_token_info.access_token

    def get_project_id(self, credentials_path: str) -> str:
        with open(credentials_path, "r") as f:
            json_ = json.loads(
                f.read(),
            )
            return json_["project_id"]

    def get_version_id(self, access_token: str, project_id: str) -> str:
        API_ENDPOINT = f"https://firebasehosting.googleapis.com/v1beta1/sites/{project_id}/versions"

        headers = {
            "Content-Type": "application/json",
            "Content-Length": "134",
            "Authorization": f"Bearer {access_token}",
        }

        _json = {
            "config": {
                "headers": [
                    {
                        "glob": "**",
                        "headers": {
                            "Cache-Control": "max-age=1800"
                        }
                    }
                ]
            }
        }

        r = requests.post(API_ENDPOINT, headers=headers, json=_json)
        print(f"[firebase-hosting] {r.status_code}, {r.text}")

        if r.status_code == 200:
            data = json.loads(r.text)
            name = data['name']

            version_id = extract_version_id(name)
            return version_id

    def populate_files(self, access_token: str, project_id: str, version_id: str, files: list, base_dir: str) -> int:
        API_ENDPOINT = f"https://firebasehosting.googleapis.com/v1beta1/sites/{project_id}/versions/{version_id}:populateFiles"

        headers = {
            "Content-Type": "application/json",
            "Content-Length": "181",
            "Authorization": f"Bearer {access_token}",
        }

        _json = {
            "files": {}
        }

        _data = {}

        for file in files:
            hash = file["hash"]

            gzip_path = file["path"]

            original_path = file["path"]
            original_path = original_path.replace(".gz", "")

            _json["files"][original_path] = hash

            _data[hash] = gzip_path

        r = requests.post(API_ENDPOINT, headers=headers, json=_json)
        print(f"[firebase-hosting] {r.status_code}, {r.text}")

        if r.status_code == 200:
            data = json.loads(r.text)
            hashes = data["uploadRequiredHashes"]
            upload_url = data["uploadUrl"]

            for hash in hashes:
                self.upload_file(
                    access_token=access_token, upload_url=upload_url, hash=hash, file_path=_data[
                        hash], base_dir=base_dir,
                )

        self.update_version_status(
            access_token=access_token, project_id=project_id, version_id=version_id,
        )
        return self.release_version(access_token=access_token, project_id=project_id, version_id=version_id)

    def upload_file(self, access_token: str, upload_url: str, hash: str, file_path: str, base_dir: str) -> None:
        API_ENDPOINT = f"{upload_url}/{hash}"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/octet-stream",
            "Content-Length": "500"
        }

        file_path = file_path[1:]
        f = open(f"{base_dir}/gzip/{file_path}", "rb")
        bytes = f.read()
        f.close()

        print(
            f"[firebase-hosting] Uploading file {file_path} to URL {API_ENDPOINT}",
        )

        r = requests.post(API_ENDPOINT, headers=headers, data=bytes)
        print(f"[firebase-hosting] {r.status_code}", end="\n")

    def update_version_status(self, access_token: str, project_id: str, version_id: str, status: str = "FINALIZED") -> int:
        API_ENDPOINT = f"https://firebasehosting.googleapis.com/v1beta1/sites/{project_id}/versions/{version_id}?update_mask=status"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Content-Length": "23"
        }

        _json = {
            "status": status,
        }

        r = requests.patch(API_ENDPOINT, headers=headers, json=_json)
        print(f"[firebase-hosting] {r.status_code}, {r.text}")

        return r.status_code

    def release_version(self, access_token: str, project_id: str, version_id: str) -> int:
        API_ENDPOINT = f"https://firebasehosting.googleapis.com/v1beta1/sites/{project_id}/releases?versionName=sites/{project_id}/versions/{version_id}"

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        r = requests.post(API_ENDPOINT, headers=headers)
        print(f"[firebase-hosting] {r.status_code}, {r.text}")
        return r.status_code


def extract_version_id(name: str) -> str:
    if not name:
        return None

    name_segments = name.split("/")
    return name_segments[-1]
