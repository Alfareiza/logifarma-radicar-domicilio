from pathlib import Path

from PIL import Image, ImageOps


class ImgHelper:
    def __init__(self, filepath: str):
        if self.file_exists(filepath):
            self.filepath: Path = Path(filepath)
            self.new_filepath: Path = None  # Creado en save
            self.name: str = self.filepath.stem
            self.ext: str = self.filepath.suffix
        else:
            raise FileNotFoundError(filepath)

        img = Image.open(filepath)
        self.img = ImageOps.exif_transpose(img)
        self.fp = img.fp

    @staticmethod
    def file_exists(filepath):
        file = Path(filepath)
        return file.exists()

    def convert_to_grayscale(self):
        self.img = self.img.convert("L")

    def save(self, filepath: Path = None, quality=20, optimize=True):
        if not filepath:
            filepath = str(self.filepath.parent / f"{self.name}_new{self.ext}")

        self.new_filepath = Path(filepath)

        self.img.save(fp=filepath, quality=quality, optimize=optimize)


if __name__ == '__main__':
    fp = input('Digite filepath de imagen: ')
    img = ImgHelper(fp)
    img.convert_to_grayscale()
    img.save()
