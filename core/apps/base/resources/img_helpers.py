from pathlib import Path

from PIL import Image


class ImgHelper:
    def __init__(self, filepath: str):
        if self.file_exists(filepath):
            self.filepath: Path = Path(filepath)
            self.name: str = self.filepath.stem
            self.ext: str = self.filepath.suffix
        else:
            raise FileNotFoundError()

        self.img = Image.open(filepath)
        self.fp = self.img.fp

    @staticmethod
    def file_exists(filepath):
        file = Path(filepath)
        if file.exists():
            return True
        return False

    def convert_to_grayscale(self):
        self.img = self.img.convert("L")

    def save(self, filepath=None, quality=20, optimize=True):
        if not filepath:
            filepath = str(self.filepath.parents[0] / f"{self.name}_new{self.ext}")

        self.img.save(fp=filepath,
                      quality=quality, optimize=optimize)


if __name__ == '__main__':
    fp = input('Digite filepath de imagen: ')
    img = ImgHelper(fp)
    img.convert_to_grayscale()
    img.save()
