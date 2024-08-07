"""
File Explorer Web Application

This Flask application serves as a simple file explorer allowing users to navigate through directories,
view file metadata, search for files, and retrieve selected file paths.

"""

import datetime
import functools
import os
import secrets
import shutil
from pathlib import Path
from secrets import compare_digest

from flask import (
    Flask,
    render_template,
    abort,
    request,
    url_for,
    redirect,
    session,
    flash,
)


def create_app():

    app = Flask(__name__)
    app.secret_key = secrets.token_urlsafe(32)

    # Before each request, set a new random secret key for the session
    @app.before_request
    def set_session_secret_key():
        if "secret_key" not in session:
            session["secret_key"] = secrets.token_urlsafe(32)

    def get_user_folder_path():
        """
        Determine the user's home directory based on the operating system.

        Returns:
            str: User's home directory path.
        """
        if os.name == "posix":  # Unix-based OS (Linux, macOS)
            return os.path.join("/", "home")
        elif os.name == "nt":  # Windows
            return os.path.join("C:", "\\", "Users")
        else:
            return "/"  # Default to root for other OS types

    BASE_DIR = str(get_user_folder_path())

    def get_sorted_files(directory):
        """
        Get a sorted list of directories and files in the given directory.

        Args:
            directory (Path): The directory path.

        Returns:
            list: Sorted list of directories and files.
        """
        items = []
        directory = Path(directory).resolve()

        try:
            items = list(directory.iterdir())
        except (PermissionError, FileNotFoundError, Exception) as e:
            app.logger.warning(f"Error accessing directory: {e}")
            flash(f"Error accessing directory: {e}")
            directory = directory.parent
            items = list(directory.iterdir())

        dirs = []  # List to store unique directory names
        files = []  # List to store file names

        # Set to store directory names to avoid repetition
        seen_dirs = set()
        seen_files = set()

        for item in items:
            if (
                item.is_dir() or item.is_file()
            ):  # Check if the item is either a directory or a file
                real_path = item
                name = real_path.name  # Get the name of the item

                # Exclude files and folders that start with a dot
                if not name.startswith("."):
                    if (
                        real_path != directory
                    ):  # Exclude the current directory from the list
                        if real_path.is_dir():  # Check if the item is a directory
                            if (
                                name not in seen_dirs
                            ):  # Check if the directory name is not repeated
                                dirs.append(
                                    name
                                )  # Append the directory name to the list of directories
                                seen_dirs.add(
                                    name
                                )  # Add the directory name to the set of seen directories
                        elif real_path.is_file():  # Check if the item is a file
                            if (
                                name not in seen_files
                            ):  # Check if the directory name is not repeated
                                files.append(
                                    name
                                )  # Append the file name to the list of files
                                seen_files.add(
                                    name
                                )  # Add the file name to the set of seen files

        return sorted(list(seen_dirs)) + sorted(list(seen_files)), directory

    @app.template_filter("format_file_size")
    def format_file_size(size_in_bytes):
        """
        Format the file size in bytes to a human-readable string.

        Args:
            size_in_bytes (float): File size in bytes.

        Returnse
            str: Formatted file size with units.
        """
        for unit in ["B", "KB", "MB", "GB"]:
            if size_in_bytes < 1024.0:
                break
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} {unit}"

    @app.template_filter("datetimeformat")
    def datetimeformat(value, format="%Y-%m-%d %H:%M:%S"):
        """
        Format the given timestamp to a string using the specified format.

        Args:
            value (float): Timestamp.
            format (str): Format string.

        Returns:
            str: Formatted datetime string.
        """
        return datetime.datetime.fromtimestamp(value).strftime(format)

    def get_file_info(file_path):
        """
        Get information about a file.

        Args:
            file_path (Path): Path to the file.

        Returns:
            dict: File information dictionary.
        """
        stat_info = os.stat(file_path)

        file_info = {
            "File Path": str(file_path),
            "File Size": format_file_size(stat_info.st_size),
            "Last Modified": stat_info.st_mtime,
            "Is Directory": os.path.isdir(file_path),
            "Is File": os.path.isfile(file_path),
            "File Extension": str(file_path).split(".")[-1],
            "File Permissions": oct(stat_info.st_mode)[-3:],
            "Path Components": file_path.parts,
        }

        return file_info

    def get_users():
        return os.listdir(BASE_DIR)

    def login_required(route):
        users_info = get_users()

        @functools.wraps(route)
        def route_wrapper(*args, **kwargs):
            if "username" not in session or session["username"] not in users_info:
                print("Please log in to access this page.", "error")
                flash("Please log in to access this page.", "error")
                return redirect(url_for("login"))
            return route(*args, **kwargs)

        return route_wrapper

    def get_unix_path(path_dir):
        if os.name == "posix" and str(path_dir)[0] != "/":
            return Path("/" + path_dir)

        return Path(path_dir)

    # Login route
    @app.route("/")
    @app.route("/login/", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form["user"]
            password = request.form["pswd"]

            users_info = {user: 12345 for user in get_users()}

            # Check if username and password match
            if username in users_info and compare_digest(
                str(users_info[username]), password
            ):
                session["username"] = username  # Store username in session
                flash("Logged in successfully!", "success")
                rel_directory = str(os.path.join(BASE_DIR, username))
                return redirect(url_for("index", rel_directory=rel_directory))
            else:
                flash("Invalid username or password", "error")
                return redirect(url_for("login"))

        return render_template("login.html")

    @app.route("/index/<path:rel_directory>/")
    @login_required
    def index(rel_directory):
        """
        Render the home page or directory listing page.

        Args:
            rel_directory (str): Relative path of the directory.

        Returns:
            render_template: Rendered HTML template.
        """

        rel_directory = get_unix_path(rel_directory)

        files, current_directory = get_sorted_files(rel_directory)

        return render_template(
            "index.html", files=files, current_directory=current_directory.resolve()
        )

    # Logout route
    @app.route("/logout/", methods=["POST"])
    def logout():
        session.pop("username", None)  # Remove username from session
        flash("Logged out successfully!", "success")
        return redirect(url_for("login"))

    @app.route("/view_file/<path:filepath>/", methods=["GET", "POST"])
    # @login_required
    def view_file(filepath):
        """
        Render the page for viewing file metadata.

        Args:
            filepath (str): Path to the file.

        Returns:
            render_template: Rendered HTML template.
        """
        file_path = Path(get_unix_path(filepath))

        if not file_path.exists():
            app.logger.info(f"The file '{file_path}' does not exist.")
            flash(f"The file '{file_path}' does not exist.")
            abort(404)

        app.logger.info(f"Viewing metadata for file: {file_path}")

        file_info = get_file_info(file_path)

        # Handle POST request to retrieve file path
        if request.method == "POST":
            # Logic to retrieve the file path goes here
            file_path_to_display = str(file_path)

            # Render the template with the file path to display
            return render_template(
                "view_file.html",
                file_path=file_path.resolve(),
                file_info=file_info,
                file_path_to_display=file_path_to_display,
            )

        # Render the template for a regular GET request
        return render_template(
            "view_file.html", file_path=file_path.resolve(), file_info=file_info
        )

    def search_files(directory, query, depth=3):
        """
        Search for files in the specified directory matching the given query.

        Args:
            directory (Path): Directory to search.
            query (str): Search query.
            depth (int): Depth of recursive search.

        Returns:
            list: List of search results.
        """
        results = []

        def recursive_search(path, current_depth):
            if current_depth > depth:
                return

            for item in path.iterdir():
                try:
                    if query.lower() in item.name.lower():
                        results.append(
                            {
                                "name": item.name,
                                "path": str(item.resolve()),
                                "is_file": item.is_file(),
                                "size": (
                                    format_file_size(item.stat().st_size)
                                    if item.is_file()
                                    else None
                                ),
                                "last_modified": (
                                    datetime.datetime.fromtimestamp(
                                        item.stat().st_mtime
                                    ).strftime("%Y-%m-%d %H:%M:%S")
                                    if item.is_file()
                                    else None
                                ),
                            }
                        )
                    if item.is_dir():
                        recursive_search(
                            item, current_depth + 1
                        )  # Recursively search in subdirectories
                except PermissionError:
                    continue

        recursive_search(directory, 0)
        return results

    @app.route("/search/")
    # @login_required
    def search():
        """
        Render the page with search results.

        Returns:
            render_template: Rendered HTML template.
        """
        query = request.args.get("query", "")
        abs_directory = request.args.get("dir", BASE_DIR)
        current_directory = Path(abs_directory)
        search_results = search_files(current_directory, query)
        return render_template(
            "search_results.html",
            files=search_results,
            current_directory=current_directory.resolve(),
            query=query,
        )

    @app.route("/retrieve_selected_file_path/", methods=["POST"])
    # @login_required
    def retrieve_selected_file_path():
        """
        Render the page with retrieved selected file paths.

        Returns:
            render_template: Rendered HTML template.
        """
        selected_files = request.form.getlist("selected_files")
        return render_template(
            "selected_file_paths.html", selected_files=selected_files
        )

    # Upload route
    @app.route("/upload/<path:current_directory>/", methods=["POST"])
    # @login_required
    def upload(current_directory):
        if "file" not in request.files:
            flash("No file part", "error")
            return redirect(request.url)

        file = request.files["file"]

        if file.filename == "":
            flash("No selected file", "error")
            return redirect(request.url)

        if file:
            # Save the uploaded file to the current directory
            current_directory = get_unix_path(current_directory)
            file.save(os.path.join(current_directory, file.filename))
            flash("File uploaded successfully!", "success")
            return redirect(url_for("index", rel_directory=current_directory))
        else:
            flash("Error uploading file", "error")
            return redirect(request.url)

    @app.route("/delete_file_or_directory/", methods=["POST"])
    # @login_required
    def delete_file_or_directory():
        if request.method == "POST":
            path = request.form.get("path")
            current_directory = request.form.get(
                "current_directory"
            )  # Retrieve current directory from form data
            current_directory = get_unix_path(current_directory)
            # current_directory = request.referrer
            try:
                if os.path.exists(path):
                    if os.path.isfile(path):
                        os.remove(path)
                        flash("File deleted successfully!", "success")
                    elif os.path.isdir(path):
                        shutil.rmtree(path)
                        flash("Directory deleted successfully!", "success")
                else:
                    flash("File or directory does not exist.", "error")
            except Exception as e:
                app.logger.error(f"Error deleting file/directory: {e}")
                flash("An error occurred while deleting the file/directory.", e)

        return redirect(url_for("index", rel_directory=current_directory))

    return app


if __name__ == "__main__":
    create_app().run(debug=True)
