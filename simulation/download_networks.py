import urllib.request
import os

def download_network():
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data/networks'))
    os.makedirs(target_dir, exist_ok=True)
    filepath = os.path.join(target_dir, 'Net3.inp')

    if os.path.exists(filepath):
        print(f"Net3.inp already exists at {filepath}")
        return

    # Direct working GitHub URL
    urls = [
        'https://raw.githubusercontent.com/USEPA/WNTR/main/examples/networks/Net3.inp',
        'https://raw.githubusercontent.com/USEPA/WNTR/master/examples/networks/Net3.inp'
    ]

    for url in urls:
        print(f"Downloading Net3.inp from {url}...")
        try:
            urllib.request.urlretrieve(url, filepath)
            print(f"Saved Net3.inp to {filepath}")
            return
        except Exception as e:
            print(f"Failed download from {url}: {e}")

if __name__ == "__main__":
    download_network()


