import os


PANEL_USER = "panel"
PANEL_UID = 10001
PANEL_GID = 10001


def _chown_path(path: str, recursive: bool = False) -> None:
    if not path:
        return
    try:
        if recursive and os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                os.chown(root, PANEL_UID, PANEL_GID)
                for name in dirs:
                    os.chown(os.path.join(root, name), PANEL_UID, PANEL_GID)
                for name in files:
                    os.chown(os.path.join(root, name), PANEL_UID, PANEL_GID)
        elif os.path.exists(path):
            os.chown(path, PANEL_UID, PANEL_GID)
        if os.path.exists(path):
            mode = os.stat(path).st_mode
            os.chmod(path, mode | 0o600)
    except PermissionError:
        pass


def _ensure_file(path: str) -> None:
    if not path:
        return
    try:
        if os.path.isdir(path):
            return
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("{}\n")
    except OSError:
        pass


def _can_panel_write(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        st = os.stat(path)
    except OSError:
        return False
    return st.st_uid == PANEL_UID and bool(st.st_mode & 0o200)


def _drop_privileges() -> None:
    import grp
    import pwd

    try:
        gid = grp.getgrnam(PANEL_USER).gr_gid
        uid = pwd.getpwnam(PANEL_USER).pw_uid
    except KeyError:
        gid = PANEL_GID
        uid = PANEL_UID
    os.initgroups(PANEL_USER, gid)
    os.setgid(gid)
    os.setuid(uid)


def main() -> None:
    config_path = os.environ.get("PROXY_CONFIG_PATH", "/app/config.json")
    data_dir = os.environ.get("PROXY_DATA_DIR", "/app/data")

    os.makedirs(data_dir, exist_ok=True)
    _ensure_file(config_path)
    _chown_path(config_path)
    _chown_path(data_dir, recursive=True)

    if _can_panel_write(config_path):
        _drop_privileges()
    os.execvp(
        "uvicorn",
        ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"],
    )


if __name__ == "__main__":
    main()
