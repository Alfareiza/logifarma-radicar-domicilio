from pathlib import Path
from unittest import TestCase

from core.apps.base.resources.img_helpers import ImgHelper
from core.settings import BASE_DIR


class ImgHelperTests(TestCase):
    image_one = BASE_DIR / 'core/apps/base/tests/resources/image_1.jpg'
    image_two = BASE_DIR / 'core/apps/base/tests/resources/image_2.png'

    def del_file(self, filepath: Path):
        if not isinstance(filepath, Path):
            filepath = Path(filepath)

        filepath.unlink()

    def test_convert_to_grayscale_keeping_orientation(self):
        """Test the orientation of the file after converted to grayscale"""
        for image in (self.image_one, self.image_two):
            with self.subTest(i=image):
                img = ImgHelper(image)
                img.convert_to_grayscale()
                img.save()

                new_img = ImgHelper(img.new_filepath)

                self.assertEqual(
                    (img.img.height, img.img.width),
                    (new_img.img.height, new_img.img.width)
                )

                self.del_file(img.new_filepath)
