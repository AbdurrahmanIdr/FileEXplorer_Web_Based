"""
File Explorer Web Application

This Flask application serves as a simple file explorer allowing users to navigate through directories,
view file metadata, search for files, and retrieve selected file paths.

"""
import datetime
import os
import platform
import subprocess
from pathlib import Path

from flask import Flask, render_template, abort, request

app = Flask(__name__)


# users = {'admin': 12345}


# def login_required(route):
#  @functools.wraps(route)
# def route_wrapper(*args, **kwargs):
#  email = session['email']
#   if email or email not in users:
#     return redirect(url_for("login"))
#   return route(*args, **kwargs)

# return route_wrapper


# Function to get connected devices
def get_connected_devices():
    devices = []
    if platform.system() == 'Windows':
        # Get connected drives in Windows
        drives = subprocess.run(['wmic', 'logicaldisk', 'get', 'caption'], capture_output=True, text=True)
        drive_list = drives.stdout.split('\n')[1:-1]
        for drive in drive_list:
            devices.append(drive.strip())
    elif platform.system() == 'Linux':
        # Get mounted devices in Linux
        mounts = subprocess.run(['lsblk', '-o', 'NAME', '-n', '-l'], capture_output=True, text=True)
        mount_list = mounts.stdout.split('\n')[:-1]
        for mount in mount_list:
            devices.append(mount.strip())
    return devices


def get_user_folder_path():
    """
        Determine the user's home directory based on the operating system.

        Returns:
            str: User's home directory path.
        """
    if os.name == 'posix':  # Unix-based OS (Linux, macOS)
        return os.path.expanduser(f'~')
    elif os.name == 'nt':  # Windows
        return Path('C:\\Users')
    else:
        return '/'  # Default to root for other OS types


BASE_DIR = get_user_folder_path()


def get_sorted_files(directory):
    """
       Get a sorted list of directories and files in the given directory.

       Args:
           directory (Path): The directory path.

       Returns:
           list: Sorted list of directories and files.
       """
    items = []
    try:
        items = list(directory.iterdir())
    except (PermissionError, FileNotFoundError):
        app.logger.warning(f"PermissionError: Access is denied for '{directory}'")
        items = list(directory.parent.iterdir())

    dirs = []
    files = []

    for item in items:
        if item.is_dir() or item.is_file():
            # Resolve symbolic links to get the real path
            real_path = item.resolve()
            if real_path != directory:
                if real_path.is_dir():
                    dirs.append(real_path.name)
                elif real_path.is_file():
                    files.append(real_path.name)

    return sorted(dirs) + sorted(files)


def format_file_size(size_in_bytes):
    """
       Format the file size in bytes to a human-readable string.

       Args:
           size_in_bytes (float): File size in bytes.

       Returns:
           str: Formatted file size with units.
       """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            break
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} {unit}"


def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
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
        "File Extension": str(file_path).split('.')[-1],
        "File Permissions": oct(stat_info.st_mode)[-3:],
        "Path Components": file_path.parts,
    }

    return file_info


@app.route('/')
@app.route('/<path:rel_directory>')
def index(rel_directory='//'):
    """
       Render the home page or directory listing page.

       Args:
           rel_directory (str): Relative path of the directory.

       Returns:
           render_template: Rendered HTML template.
       """
    current_directory = Path(rel_directory)
    if rel_directory == '//':
        files = [x for x in get_connected_devices() if len(x) > 0]
        print(files)
    else:
        files = get_sorted_files(current_directory)

    return render_template('index.html', files=files, current_directory=current_directory.resolve())


@app.route('/view_file/<path:filepath>', methods=['GET', 'POST'])
def view_file(filepath):
    """
        Render the page for viewing file metadata.

        Args:
            filepath (str): Path to the file.

        Returns:
            render_template: Rendered HTML template.
        """
    file_path = Path(filepath)

    if not file_path.exists():
        app.logger.info(f"The file '{file_path}' does not exist.")
        abort(404)

    app.logger.info(f"Viewing metadata for file: {file_path}")

    file_info = get_file_info(file_path)

    # Handle POST request to retrieve file path
    if request.method == 'POST':
        # Logic to retrieve the file path goes here
        file_path_to_display = str(file_path)

        # Render the template with the file path to display
        return render_template('view_file.html', file_path=file_path.resolve(), file_info=file_info,
                               file_path_to_display=file_path_to_display)

    # Render the template for a regular GET request
    return render_template('view_file.html', file_path=file_path.resolve(), file_info=file_info)


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
                    results.append({
                        'name': item.name,
                        'path': str(item.resolve()),
                        'is_file': item.is_file(),
                        'size': format_file_size(item.stat().st_size) if item.is_file() else None,
                        'last_modified': datetime.datetime.fromtimestamp(item.stat().st_mtime).strftime(
                            '%Y-%m-%d %H:%M:%S') if item.is_file() else None,
                    })
                if item.is_dir():
                    recursive_search(item, current_depth + 1)  # Recursively search in subdirectories
            except PermissionError:
                continue

    recursive_search(directory, 0)
    return results


@app.route('/search')
def search():
    """
       Render the page with search results.

       Returns:
           render_template: Rendered HTML template.
       """
    query = request.args.get('query', '')
    abs_directory = request.args.get('dir', BASE_DIR)
    current_directory = Path(abs_directory)
    search_results = search_files(current_directory, query)
    return render_template('search_results.html', files=search_results,
                           current_directory=current_directory.resolve(), query=query)


@app.route('/retrieve_selected_file_path', methods=['POST'])
def retrieve_selected_file_path():
    """
        Render the page with retrieved selected file paths.

        Returns:
            render_template: Rendered HTML template.
        """
    selected_files = request.form.getlist('selected_files')
    return render_template('selected_file_paths.html', selected_files=selected_files)


if __name__ == '__main__':
    app.jinja_env.filters['format_file_size'] = format_file_size
    app.jinja_env.filters['datetimeformat'] = datetimeformat
    app.run(debug=True)
