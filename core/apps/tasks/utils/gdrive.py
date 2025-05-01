import csv
import io
import mimetypes
import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache

import chardet as chardet
# from dateutil.parser import parse
from decouple import config
from django.conf import settings
from django.core.files import File
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from gdstorage.storage import GoogleDriveStorage, GoogleDriveFilePermission, GoogleDrivePermissionRole, \
    GoogleDrivePermissionType
# from gdstorage.storage import GoogleDriveFilePermission, GoogleDrivePermissionRole, GoogleDrivePermissionType
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload, MediaIoBaseUpload

from core.apps.base.resources.decorators import logtime, ignore_unhashable
from core.settings import logger as log


@dataclass
class GDriveHandler:

    def __post_init__(self):
        # self.creds = Credentials.from_authorized_user_file('utils/gdrive/token.json', SCOPES)
        info = dict(token=config('GDRIVE_TOKEN'),
                    refresh_token=config('GDRIVE_REFRESH_TOKEN'),
                    client_id=config('GDRIVE_CLIENT_ID'),
                    client_secret=config('GDRIVE_CLIENT_SECRET'),
                    expiry=config('GDRIVE_EXPIRY'),
                    scopes=['https://www.googleapis.com/auth/drive'])
        self.creds = Credentials.from_authorized_user_info(info)
        self.service = build('drive', 'v3', credentials=self.creds)

    @ignore_unhashable
    @lru_cache()
    def get_folder_id_by_name(self, name) -> str:
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder'"
        response = self.service.files().list(q=query).execute()
        if folders := response.get('files', []):
            print('FOLDER ID IS -> ', folders[0]['id'])
            return folders[0]['id']
        log.warning(f'No fue encontrado folder {name}.')
        return ''

    def get_files_in_folder_by_id(self, folder_id, ext='', only_files=True) -> list:
        """
        Reach the files of a given folder given an id.
        :param only_files: Define if only files will be reached or all the elements.
        :param ext: Extension of files to  be reached.
        :param folder_id: '1Pf...Y'
        :return: Ex.:
                    [
                        {'id': '123lkj...',
                        'name': 'Dispensacion-8.csv',
                        'createdTime': '2023-06-20T14:51:22.991Z',
                        'modifiedTime': '2023-06-10T20:26:35.000Z'},
                        {'id': '456mnb...',
                        'name': 'Dispensacion-7.csv',
                        'createdTime': '2023-06-20T14:51:24.290Z',
                        'modifiedTime': '2023-06-10T15:53:34.000Z'},
                        {'id': '345pokjn...',
                        'name': 'Dispensacion-6.csv',
                        'createdTime': '2023-06-20T14:51:24.290Z',
                        'modifiedTime': '2023-06-07T22:11:25.000Z'},
                        {'id': '1m...1A',
                        'name': 'convenioArticulos062023.csv',
                        'createdTime': '2023-06-05T13:00:48.698Z',
                        'modifiedTime': '2023-06-05T13:00:48.698Z'}
                    ]
        """
        query = f"'{folder_id}' in parents and trashed = false"
        if only_files:
            query += "and mimeType != 'application/vnd.google-apps.folder'"
        if ext:
            query += f" and fileExtension='{ext}'"
        fields = 'files(id, name, modifiedTime, createdTime, parents)'
        response = self.service.files().list(q=query, fields=fields).execute()
        files = response.get('files', [])
        return self.order_files_asc(files)

    @ignore_unhashable
    @lru_cache()
    @logtime('')
    def get_files_in_folder_by_name(self, folder_name, ext=None) -> list:
        """
        Reach the files of a folder given a folder name.
        :param ext: Extension of files to  be reached.
        :param filter: Parameter who help to filter the result before return it.
                       It might have the next estructure:
                       filter = {'ext': 'csv'}
        :param folder_name: 'My Folder'
        :return: Ex.:
                      [
                        'parents': ['1-0sn...zmT1G8'],
                        {'id': '1Pf...Y',
                        'kind': 'drive#file',
                        'name': 'convenioArticulos042021.csv'},
                       {
                        'parents': ['1-0sn...zmT1G8'],
                        'id': '1Pf...Bf',
                        'name': 'convenioArticulos052021.csv'},
                       {
                         'parents': ['1-0sn...zmT1G8'],
                         'id': '1Pf...8',
                         'name': 'DonacionesMedicar'},
                         'createdTime': '2023-06-05T13:00:48.698Z',
                        'modifiedTime': '2023-06-05T13:00:48.698Z'
                       {
                        'parents': ['1-0sn...zmT1G8'],
                        'id': '1Pf...f',
                        'name': 'TrasladosMedicar'},
                        'createdTime': '2023-06-05T13:00:48.698Z',
                        'modifiedTime': '2023-06-05T13:00:48.698Z'
                       {
                         'parents': ['1-0sn...zmT1G8'],
                         'id': '1Pf...FR',
                         'name': 'FacturacionMedicar'},
                         'createdTime': '2023-06-05T13:00:48.698Z',
                        'modifiedTime': '2023-06-05T13:00:48.698Z'
                       {
                         'parents': ['1-0sn...zmT1G8'],
                         'id': '1Pf...2',
                        'createdTime': '2023-06-05T13:00:48.698Z',
                        'modifiedTime': '2023-06-05T13:00:48.698Z'
                        'name': 'DispensacionMedicar'},
                       {
                         'parents': ['1-0sn...zmT1G8'],
                         'id': '1Pf...z',
                         'name': 'convenioArticulos092021.csv',
                         'createdTime': '2023-06-05T13:00:48.698Z',
                         'modifiedTime': '2023-06-05T13:00:48.698Z'
                        }
                      ]
        """
        return self.get_files_in_folder_by_id(self.get_folder_id_by_name(folder_name), ext=ext)

    @logtime('DRIVE')
    def read_csv_file_by_id(self, file_id: str):
        file_metadata = self.service.files().get(fileId=file_id).execute()

        # Download the file content as a bytes object
        request = self.service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        # encoding = self.detect_csv_encoding(file_id)

        # Convert the bytes content to a string
        # file_content_str = file_content.getvalue().decode('utf-8-sig')
        file_content_str = file_content.getvalue().decode('latin-1')

        # Process the CSV file content using DictReader
        import csv
        from io import StringIO

        csv_data = StringIO(file_content_str)
        return csv.DictReader(csv_data, delimiter=';')

    def move_file(self, file: dict, to_folder_name: str) -> None:
        """
        Move a file to another folder.
        When it happens, might return a dict like this:
        {'kind': 'drive#file', 'id': '123kjkafF', 'name': 'file_name.csv',
        'mimeType': 'text/plain', 'parents': ['1LodKp...bBf'],
        'createdTime': '2023-07-05T22:15:43.580Z',
        'modifiedTime': '2023-07-05T21:59:16.994Z'}
        :param file: Dict with unique identification of the file in Google Drive.
        :param to_folder_name: Name of the folder where it will be moved.
        """
        new_parent_id = self.get_folder_id_by_name(to_folder_name)
        previous_parents = ",".join(file.get('parents'))
        self.service.files().update(
            fileId=file['id'], addParents=new_parent_id, removeParents=previous_parents, fields='id, parents'
        ).execute()

    def create_file_in_drive(self, name: str, content, content_type: str, folder_id: str = None,
                             folder_name: str = None) -> str:
        """
        Create file in Google Drive
        :param name: 'name of the file.png'
        :param content:
        :param content_type: 'image/png'
        :param folder_name: 'FormulasMedicas'
        :param folder_id: 'FormulasMedicas'
        :return:
        """
        log.info(f"Creando archivo {content_type!r} en Gdrive con {name=}")

        if folder_name:
            folder_id = self.get_folder_id_by_name(folder_name)

        if not folder_name and not folder_id:
            raise Exception('Missing fields either folder_id or folder_name.')

        media_body = MediaIoBaseUpload(
            content, content_type, resumable=True, chunksize=1024 * 512)
        body = {
            'name': name,
            'mimeType': content_type,
            'parents': [folder_id]
        }

        file = self.service.files().create(body=body,
                                           media_body=media_body,
                                           fields='id').execute()
        log.info(f"{name!r} creado en Gdrive con id={file['id']!r}")
        if file:
            return file['id']
        return ''

    def send_csv(self, path_csv, filename, folder_name) -> None:
        """
        From a filepath, it sends the file to Google Drive.
        :param path_csv: '/Users/alfonso/Projects/SAPIntegration/dispensacion_processed.csv'
        :param filename: Name of the file.
        :param folder_name: Name of the folder where the file will be placed.
        :return:
        """
        log.info("Preparando envio de csv para GDrive.")
        folder_id = self.get_folder_id_by_name(folder_name)
        file_metadata = {'name': filename, 'parents': [folder_id]}
        media = MediaFileUpload(path_csv, mimetype='text/plain')
        file = self.service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        log.info(f"CSV {filename!r} creado en carpeta {folder_name!r} con ID: {file['id']}")

    def detect_csv_encoding(self, file_id):
        request = self.service.files().get_media(fileId=file_id)
        response = request.execute()

        content = response.decode('utf-8')  # Decode the content to a string
        detector = chardet.UniversalDetector()

        # Feed the content to the detector line by line
        for line in content.splitlines():
            detector.feed(line.encode('raw_unicode_escape'))
            if detector.done:
                break

        detector.close()
        return detector.result['encoding']

    def order_files_asc(self, lst_files):
        """
        Given a list of files, return the same list
        with the items ordered by createdTime.
        :param lst_files:
                    Ex.:
                        [
                            {'id': '123lkj...',
                            'name': 'Dispensacion-8.csv',
                            'createdTime': '2023-06-20T14:51:22.991Z',
                            'modifiedTime': '2023-06-10T20:26:35.000Z'},
                            {'id': '456mnb...',
                            'name': 'Dispensacion-7.csv',
                            'createdTime': '2023-06-20T14:51:24.290Z',
                            'modifiedTime': '2023-06-10T15:53:34.000Z'},
                            {'id': '345pokjn...',
                            'name': 'Dispensacion-6.csv',
                            'createdTime': '2023-06-20T14:51:24.290Z',
                            'modifiedTime': '2023-06-07T22:11:25.000Z'},
                            {'id': '1m...1A',
                            'name': 'convenioArticulos062023.csv',
                            'createdTime': '2023-06-05T13:00:48.698Z',
                            'modifiedTime': '2023-06-05T13:00:48.698Z'}
                        ]
        :return:
        """
        # TODO
        return lst_files


class CustomGoogleDriveStorage(GoogleDriveStorage):
    def __init__(self):
        super().__init__()
        self._permissions = (GoogleDriveFilePermission(
            GoogleDrivePermissionRole.READER,
            GoogleDrivePermissionType.ANYONE
        ),)
        info = dict(token=config('GDRIVE_TOKEN'),
                    private_key=config('GDRIVE_TOKEN'),
                    token_uri="https://oauth2.googleapis.com/token",
                    client_email=config('GDRIVE_EMAIL_CLIENT'),
                    refresh_token=config('GDRIVE_REFRESH_TOKEN'),
                    client_id=config('GDRIVE_CLIENT_ID'),
                    client_secret=config('GDRIVE_CLIENT_SECRET'),
                    expiry=config('GDRIVE_EXPIRY'),
                    scopes=['https://www.googleapis.com/auth/drive'])
        credentials = Credentials.from_authorized_user_info(info)
        self._drive_service = build('drive', 'v3', credentials=credentials)

    # def _save(self, name, content):
    #     import threading
    #     x = threading.Thread(target=super()._save, args=(name, content))
    #     x.start()
