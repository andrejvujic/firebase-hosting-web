import json
import os
import pathlib
import shutil
from src.utils import generate_random_id, gzip_files, get_SHA256_hash
from src.firebase_hosting import FirebaseHosting
from flask import Flask, request, render_template, redirect

app = Flask(__name__)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "static", "files")
pathlib.Path(UPLOAD_FOLDER).mkdir(exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

firebase = FirebaseHosting()


def allowed_file_format(file_name: str) -> bool:
    if not file_name:
        return False

    segments = file_name.split(".")
    return segments[-1] == "json"


def clean_up_session_files(session_id: str) -> None:
    path = os.path.join(
        app.config["UPLOAD_FOLDER"], session_id,
    )

    shutil.rmtree(
        path, ignore_errors=True,
    )


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    return redirect("/createSession")


@app.route("/createSession", methods=["GET"])
def createSession():
    session_id = generate_random_id()
    return redirect(f"/session/{session_id}/chooseServiceAccountFile")


@app.route("/session/<session_id>/chooseServiceAccountFile", methods=["GET", "POST"])
def chooseServiceAccountFile(session_id: str):
    if request.method == "GET":
        return render_template("choose_service_account_file.html", session_id=session_id)

    files = request.files

    if not files:
        return render_template("error.html", message="No files were uploaded to the server.")

    service_account_file = files["service-account-file"]

    if not service_account_file:
        return render_template("error.html", message="No service account file was provided.")

    if not allowed_file_format(service_account_file.filename):
        return render_template("error.html", message="Error while parsing, service account file must be a JSON file.")

    os.mkdir(
        os.path.join(
            app.config['UPLOAD_FOLDER'], session_id,
        )
    )

    service_account_file_path = os.path.join(
        app.config["UPLOAD_FOLDER"], session_id, "service-account.json",
    )

    service_account_file.save(
        service_account_file_path,
    )

    return redirect(
        f"/session/{session_id}/authenticate",
    )


@app.route("/session/<session_id>/authenticate")
def authenticateUsingGoogleCloud(session_id: str):
    service_account_file_path = os.path.join(
        app.config["UPLOAD_FOLDER"], session_id, "service-account.json",
    )

    if not service_account_file_path or not os.path.isfile(service_account_file_path):
        return render_template("error.html", message="Service account file wasn't provided or doesn't exist.")
    try:

        project_id = firebase.get_project_id(
            service_account_file_path,
        )

        access_token = firebase.get_access_token(
            credentials_path=service_account_file_path,
        )

        return redirect(
            f"/session/{session_id}/deleteServiceAccountFile?projectId={project_id}&accessToken={access_token}"
        )
    except Exception:
        return render_template("error.html", message="We ran into an error while try to authenticate, please try again later.")


@app.route("/session/<session_id>/deleteServiceAccountFile")
def deleteServiceAccountFile(session_id: str):
    args = request.args
    access_token = args.get("accessToken")
    project_id = args.get("projectId")

    service_account_file_path = os.path.join(
        app.config["UPLOAD_FOLDER"], session_id, "service-account.json",
    )

    if os.path.isfile(service_account_file_path):
        os.remove(service_account_file_path)

    return redirect(f"/session/{session_id}/chooseFolder?projectId={project_id}&accessToken={access_token}") if access_token else render_template("error.html", "We ran into an error while try to authenticate, please try again later.")


@app.route("/session/<session_id>/chooseFolder", methods=["GET", "POST"])
def chooseFolderForUpload(session_id: str):
    args = request.args
    access_token = args.get("accessToken")
    project_id = args.get("projectId")

    if not access_token:
        return render_template("error.html", message="Authentication failed, no access token found, please try again.")

    if request.method == "GET":
        return render_template("choose_folder.html")

    files = request.files
    files = files.getlist("files-to-upload")

    if not files:
        return render_template("error.html", message="The selected folder doesn't contain any files.")

    for _ in files:
        name = _.filename.split(os.path.sep)
        name = name[-1]

        path = os.path.join(
            app.config["UPLOAD_FOLDER"], session_id, name,
        )
        _.save(path)

    return redirect(f"/session/{session_id}/gzipFiles?projectId={project_id}&accessToken={access_token}")


@app.route("/session/<session_id>/gzipFiles", methods=["GET"])
def gzipFiles(session_id: str):
    args = request.args
    access_token = args.get("accessToken")
    project_id = args.get("projectId")

    folder_path = os.path.join(
        app.config["UPLOAD_FOLDER"], session_id,
    )
    output_path = os.path.join(
        folder_path, "gzip",
    )

    gzip_files(
        folder_path=folder_path,
        output_path=output_path,
    )

    return redirect(
        f"/session/{session_id}/uploadFiles?projectId={project_id}&accessToken={access_token}"
    )


@app.route("/session/<session_id>/uploadFiles", methods=["GET"])
def uploadFiles(session_id: str):
    args = request.args
    access_token = args.get("accessToken")
    project_id = args.get("projectId")

    versionId = firebase.get_version_id(
        access_token=access_token, project_id=project_id,
    )

    folder_path = os.path.join(
        app.config["UPLOAD_FOLDER"], session_id,
    )
    output_path = os.path.join(
        folder_path, "gzip"
    )

    files_ = []
    files = os.listdir(output_path)

    for file in files:
        info = {}
        info["path"] = f"/{file}"
        info["hash"] = get_SHA256_hash(f"{output_path}/{file}")

        files_.append(info)

    firebase.populate_files(
        access_token=access_token, project_id=project_id, version_id=versionId,
        files=files_, base_dir=folder_path,
    )

    return redirect(f"/session/{session_id}/cleanUp?projectId={project_id}")


@app.route("/session/<session_id>/cleanUp", methods=["GET"])
def cleanUp(session_id: str):
    args = request.args
    project_id = args.get("projectId")

    clean_up_session_files(session_id=session_id)

    return redirect(f"/showSiteLinks?projectId={project_id}")


@app.route("/showSiteLinks", methods=["GET"])
def showSiteLinks():
    args = request.args
    project_id = args.get("projectId")

    if not project_id:
        return render_template(
            "error.html", message="Couldn't show site links due to an error.",
        )

    return render_template("links.html", project_id=project_id)


if __name__ == "__main__":
    app.run()
