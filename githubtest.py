import requests
import pyperclip


def get_public_repo_contents(user, repo, path=""):
    url = f"https://api.github.com/repos/{user}/{repo}/contents/{path}"
    print(f"|==Debug==| Requesting GitHub URL: {url}")
    res = requests.get(url)
    print(f"|==Debug==| Response Code:{res.status_code}")
    if res.status_code == 200:
        contents = res.json()
        items = []
        for item in contents:
            if item["type"] == "file":
                file_contents = get_file_contents(item["download_url"])
                item_data = {"name": item["name"], "content": file_contents, "path": path}
                items.append(item_data)
            elif item["type"] == "dir":
                subdir_items = get_public_repo_contents(user, repo, item["path"])
                for subdir_item in subdir_items:
                    subdir_item["path"] = f"{path}/{subdir_item['path']}"
                items.extend(subdir_items)
                dir_data = {"name": item["name"], "path": path}
                items.append(dir_data)
        return items
    else:
        print(f"Error: {res.status_code}")
        return []


def get_file_contents(url):
    res = requests.get(url)
    if res.status_code == 200:
        return res.text
    else:
        print(f"Error: {res.status_code}")
        return ""


def main():
    username = "xXenithx"
    repo = "aichatbot"
    items = get_public_repo_contents(username, repo)
    pyperclip.copy(str(items))
    # print(items)
    # for item in items:
    #     if "content" in item:
    #         print(f"File: {item['path']}/{item['name']}")
    #         print(f"Content:\n{item['content']}")
    #         print("\n")
    #     else:
    #         print(f"Folder: {item['path']}/{item['name']}\n")


if __name__ == "__main__":
    main()
