import datetime

from flask import Flask, render_template, abort, request, redirect
import os
from pathlib import Path

from passlib import pwd

app = Flask(__name__)


def get_user_folder_path():
    # Determine the user's file system based on the OS type
    if os.name == 'posix':  # Unix-based OS (Linux, macOS)
        BASE_DIR = os.path.expanduser(f'~')
    elif os.name == 'nt':  # Windows
        BASE_DIR = os.path.join('C:\\', 'Users')
    else:
        BASE_DIR = '/'  # Default to root for other OS types

    return BASE_DIR


BASE_DIR = get_user_folder_path()


def get_sorted_files(directory):
    items = []
    parent = directory.parent
    try:
        items = list(directory.iterdir())
    except PermissionError:
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
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            break
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} {unit}"


def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
    return datetime.datetime.fromtimestamp(value).strftime(format)


def get_file_info(file_path):
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
def index(rel_directory=BASE_DIR):
    abs_directory = rel_directory
    current_directory = Path(abs_directory)
    files = get_sorted_files(current_directory)

    return render_template('index.html', files=files, current_directory=current_directory.resolve())


@app.route('/view_file/<path:filepath>', methods=['GET', 'POST'])
def view_file(filepath):
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
    query = request.args.get('query', '')
    abs_directory = request.args.get('dir', BASE_DIR)
    current_directory = Path(abs_directory)
    search_results = search_files(current_directory, query)
    return render_template('search_results.html', files=search_results,
                           current_directory=current_directory.resolve(), query=query)


@app.route('/retrieve_selected_file_path', methods=['POST'])
def retrieve_selected_file_path():
    selected_files = request.form.getlist('selected_files')
    return render_template('selected_file_paths.html', selected_files=selected_files)


if __name__ == '__main__':
    app.jinja_env.filters['format_file_size'] = format_file_size
    app.jinja_env.filters['datetimeformat'] = datetimeformat
    app.run(debug=True)
