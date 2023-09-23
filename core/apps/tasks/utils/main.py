from core.apps.tasks.utils.gdrive import GDriveHandler
from core.apps.tasks.utils.pipeline import Csv2Dict, DataToDB, FillExtraDataMedicar, FillExtraDataFbase, Send2Cajacopi
from core.apps.tasks.utils.tools import moment
from core.settings import logger as log


class Dispensacion:

    def __init__(self):
        self.pipeline = [Csv2Dict, DataToDB, FillExtraDataMedicar, FillExtraDataFbase, Send2Cajacopi]
        self.client = GDriveHandler()
        self.data = {}
        self.name = self.create_name()

    def run(self):
        files = self.client.get_files_in_folder_by_name('dispensacion', ext='csv')

        if self.file_exists(self.name, files):
            file_id = [file['id'] for file in files if file['name'] == self.name]
            csv_reader = self.client.read_csv_file_by_id(file_id[0])
            for pipe in self.pipeline:
                pipe().run(data=self.data, csv_reader=csv_reader)
        else:
            log.info(f'Archivo {self.name} no existe.')

    def create_name(self):
        now = moment()
        return f"convenioArticulos{now.month:02d}{now.year}.csv"

    def file_exists(self, name, files):
        return name in [file['name'] for file in files]
