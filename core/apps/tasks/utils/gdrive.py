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

# _ANYONE_CAN_READ_PERMISSION_ = GoogleDriveFilePermission(
#     GoogleDrivePermissionRole.READER,
#     GoogleDrivePermissionType.ANYONE
# )


# @deconstructible
# class CustomGoogleDriveStorage(Storage):
#     """
#     Storage class for Django that interacts with Google Drive as persistent
#     storage.
#     This class uses a system account for Google API that create an
#     application drive (the drive is not owned by any Google User, but it is
#     owned by the application declared on Google API console).
#     In order to configure :
#     file_storage = CustomGoogleDriveStorage()
#     """
#
#     _UNKNOWN_MIMETYPE_ = 'application/octet-stream'
#     _GOOGLE_DRIVE_FOLDER_MIMETYPE_ = 'application/vnd.google-apps.folder'
#     KEY_FILE_PATH = 'GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE'
#     KEY_FILE_CONTENT = 'GOOGLE_DRIVE_STORAGE_JSON_KEY_FILE_CONTENTS'
#
#     def __init__(self, *args, **kwargs):
#         info = dict(token=config('GDRIVE_TOKEN'),
#                     refresh_token=config('GDRIVE_REFRESH_TOKEN'),
#                     client_id=config('GDRIVE_CLIENT_ID'),
#                     client_secret=config('GDRIVE_CLIENT_SECRET'),
#                     expiry=config('GDRIVE_EXPIRY'),
#                     scopes=['https://www.googleapis.com/auth/drive'])
#         credentials = Credentials.from_authorized_user_info(info)
#         self._permissions = (_ANYONE_CAN_READ_PERMISSION_,)
#         self._drive_service = build('drive', 'v3', credentials=credentials)
#
#     def _split_path(self, p):
#         """
#         Split a complete path in a list of strings
#
#         :param p: Path to be splitted
#         :type p: string
#         :returns: list - List of strings that composes the path
#         """
#         p = p[1:] if p[0] == '/' else p
#         a, b = os.path.split(p)
#         return (self._split_path(a) if len(a) and len(b) else []) + [b]
#
#     def _get_or_create_folder(self, path, parent_id=None):
#         """
#         Create a folder on Google Drive.
#         It creates folders recursively.
#         If the folder already exists, it retrieves only the unique identifier.
#
#         :param path: Path that had to be created
#         :type path: string
#         :param parent_id: Unique identifier for its parent (folder)
#         :type parent_id: string
#         :returns: dict
#         """
#         folder_data = self._check_file_exists(path, parent_id)
#         if folder_data is not None:
#             return folder_data
#
#         # Folder does not exists, have to create
#         split_path = self._split_path(path)
#
#         if split_path[:-1]:
#             parent_path = os.path.join(*split_path[:-1])
#             current_folder_data = self._get_or_create_folder(
#                 parent_path, parent_id=parent_id
#             )
#         else:
#             current_folder_data = None
#
#         meta_data = {
#             'name': split_path[-1],
#             'mimeType': self._GOOGLE_DRIVE_FOLDER_MIMETYPE_
#         }
#         if current_folder_data is not None:
#             meta_data['parents'] = [current_folder_data['id']]
#         else:
#             # This is the first iteration loop so we have to set
#             # the parent_id obtained by the user, if available
#             if parent_id is not None:
#                 meta_data['parents'] = [parent_id]
#         current_folder_data = self._drive_service.files().create(
#             body=meta_data).execute()
#         return current_folder_data
#
#     def _check_file_exists(self, filename, parent_id=None):
#         """
#         Check if a file with specific parameters exists in Google Drive.
#         :param filename: File or folder to search
#         :type filename: string
#         :param parent_id: Unique identifier for its parent (folder)
#         :type parent_id: string
#         :returns: dict containing file / folder data if exists or None if does not exists
#         """  # noqa: E501
#         if len(filename) == 0:
#             # This is the lack of directory at the beginning of a 'file.txt'
#             # Since the target file lacks directories, the assumption
#             # is that it belongs at '/'
#             return self._drive_service.files().get(fileId='root').execute()
#         split_filename = self._split_path(filename)
#         if len(split_filename) > 1:
#             # This is an absolute path with folder inside
#             # First check if the first element exists as a folder
#             # If so call the method recursively with next portion of path
#             # Otherwise the path does not exists hence
#             # the file does not exists
#             q = "mimeType = '{0}' and name = '{1}'".format(
#                 self._GOOGLE_DRIVE_FOLDER_MIMETYPE_, split_filename[0],
#             )
#             if parent_id is not None:
#                 q = "{0} and '{1}' in parents".format(q, parent_id)
#             results = self._drive_service.files().list(
#                 q=q, fields='nextPageToken, files(*)').execute()
#             items = results.get('files', [])
#             for item in items:
#                 if item['name'] == split_filename[0]:
#                     # Assuming every folder has a single parent
#                     return self._check_file_exists(
#                         os.path.sep.join(split_filename[1:]), item['id'])
#             return None
#         # This is a file, checking if exists
#         q = "name = '{0}'".format(split_filename[0])
#         if parent_id is not None:
#             q = "{0} and '{1}' in parents".format(q, parent_id)
#         results = self._drive_service.files().list(
#             q=q, fields='nextPageToken, files(*)').execute()
#         items = results.get('files', [])
#         if len(items) > 0:
#             return items[0]
#         q = '' if parent_id is None else "'{0}' in parents".format(parent_id)
#         results = self._drive_service.files().list(
#             q=q, fields='nextPageToken, files(*)').execute()
#         items = results.get('files', [])
#         for item in items:
#             if split_filename[0] in item['name']:
#                 return item
#         return None
#
#     # Methods that had to be implemented
#     # to create a valid storage for Django
#
#     def _open(self, name, mode='rb'):
#         """For more details see
#         https://developers.google.com/drive/api/v3/manage-downloads?hl=id#download_a_file_stored_on_google_drive
#         """  # noqa: E501
#         file_data = self._check_file_exists(name)
#         request = self._drive_service.files().get_media(
#             fileId=file_data['id'])
#         fh = io.BytesIO()
#         downloader = MediaIoBaseDownload(fh, request)
#         done = False
#         while done is False:
#             _, done = downloader.next_chunk()
#         fh.seek(0)
#         return File(fh, name)
#
#     def _save(self, name, content):
#         """
#         Create the file into the Google Drive folder specified on
#         GOOGLE_DRIVE_STORAGE_MEDIA_ROOT on settings.
#         :param name:
#         :param content:
#         :return:
#         """
#         name = os.path.join(settings.GOOGLE_DRIVE_STORAGE_MEDIA_ROOT, name)
#         folder_path = os.path.sep.join(self._split_path(name)[:-1])
#         folder_data = self._get_or_create_folder(folder_path)
#         parent_id = None if folder_data is None else folder_data['id']
#         # Now we had created (or obtained) folder on GDrive
#         # Upload the file
#         mime_type, _ = mimetypes.guess_type(name)
#         if mime_type is None:
#             mime_type = self._UNKNOWN_MIMETYPE_
#         media_body = MediaIoBaseUpload(
#             content.file, mime_type, resumable=True, chunksize=1024 * 512)
#         body = {
#             'name': self._split_path(name)[-1],
#             'mimeType': mime_type
#         }
#         # Set the parent folder.
#         if parent_id:
#             body['parents'] = [parent_id]
#
#         # Create file into the drive
#         file_data = self._drive_service.files().create(
#             body=body,
#             media_body=media_body).execute()
#
#         # Setting up permissions
#         for p in self._permissions:
#             self._drive_service.permissions().create(
#                 fileId=file_data['id'], body={**p.raw}).execute()
#
#         return self._split_path(name)[-1]
#         # return file_data.get('originalFilename', file_data.get('name'))
#
#     def delete(self, name):
#         """
#         Deletes the specified file from the storage system.
#         """
#         file_data = self._check_file_exists(name)
#         if file_data is not None:
#             self._drive_service.files().delete(
#                 fileId=file_data['id']).execute()
#
#     def exists(self, name):
#         """
#         Returns True if a file referenced by the given name already exists
#         in the storage system, or False if the name is available for
#         a new file.
#         """
#         return self._check_file_exists(name) is not None
#
#     def listdir(self, path):
#         """
#         Lists the contents of the specified path, returning a 2-tuple of lists;
#         the first item being directories, the second item being files.
#         """
#         directories, files = [], []
#         if path == '/':
#             folder_id = {'id': 'root'}
#         else:
#             folder_id = self._check_file_exists(path)
#         if folder_id:
#             file_params = {
#                 'q': "'{0}' in parents and mimeType != '{1}'".format(
#                     folder_id['id'], self._GOOGLE_DRIVE_FOLDER_MIMETYPE_),
#             }
#             dir_params = {
#                 'q': "'{0}' in parents and mimeType = '{1}'".format(
#                     folder_id['id'], self._GOOGLE_DRIVE_FOLDER_MIMETYPE_),
#             }
#             files_results = self._drive_service.files().list(**file_params).execute()  # noqa: E501
#             dir_results = self._drive_service.files().list(**dir_params).execute()  # noqa: E501
#             files_list = files_results.get('files', [])
#             dir_list = dir_results.get('files', [])
#             for element in files_list:
#                 files.append(os.path.join(path, element['name']))
#             for element in dir_list:
#                 directories.append(os.path.join(path, element['name']))
#         return directories, files
#
#     def size(self, name):
#         """
#         Returns the total size, in bytes, of the file specified by name.
#         """
#         file_data = self._check_file_exists(name)
#         if file_data is None:
#             return 0
#         return file_data['size']
#
#     def url(self, name):
#         """
#         Returns an absolute URL where the file's contents can be accessed
#         directly by a Web browser.
#         """
#         file_data = self._check_file_exists(name)
#         if file_data is None:
#             return None
#         return file_data['webContentLink']
#
#     def accessed_time(self, name):
#         """
#         Returns the last accessed time (as datetime object) of the file
#         specified by name.
#         """
#         return self.modified_time(name)
#
#     def created_time(self, name):
#         """
#         Returns the creation time (as datetime object) of the file
#         specified by name.
#         """
#         file_data = self._check_file_exists(name)
#         if file_data is None:
#             return None
#         return parse(file_data['createdDate'])
#
#     def modified_time(self, name):
#         """
#         Returns the last modified time (as datetime object) of the file
#         specified by name.
#         """
#         file_data = self._check_file_exists(name)
#         if file_data is None:
#             return None
#         return parse(file_data['modifiedDate'])
#
#     def deconstruct(self):
#         """
#         Handle field serialization to support migration
#         """
#         name, path, args, kwargs = super().deconstruct()
#         if self._service_email is not None:
#             kwargs['service_email'] = self._service_email
#         if self._json_keyfile_path is not None:
#             kwargs['json_keyfile_path'] = self._json_keyfile_path
#         return name, path, args, kwargs
