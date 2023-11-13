from abc import abstractmethod, ABC
from typing import Tuple

from core.apps.base.models import Radicacion
from core.apps.base.resources.email_helpers import Email
from core.apps.tasks.utils.gdrive import GDriveHandler
from core.settings import logger as log, DEBUG


class PostStep(ABC):

    @abstractmethod
    def proceed(self):
        ...


class NotifyEmail(PostStep, Email):
    def proceed(self, info_email: dict, rad_id: str) -> Tuple[bool, dict]:
        log.info(f"{info_email['log_text']} ...enviando e-mail.")
        check = False
        self.foto = info_email.get('foto', '')
        self.log_text = info_email.get('log_text')

        if self.send_mail(info_email):
            check = True
        return check, info_email


class NotifySMS(PostStep):
    def proceed(self, info_email: dict, rad_id: str) -> Tuple[bool, dict]:
        log.info(f"{info_email['log_text']} ...enviando SMS.")
        check = True
        # TODO Pendiente de implementar
        return check, info_email


class Drive(PostStep):
    def proceed(self, info_email: dict, rad_id: str) -> Tuple[bool, dict]:
        log.info(f"{info_email['log_text']} ...cargando imagen en GDrive.")
        check = False
        foto = info_email.get('foto')
        if foto and rad_id:
            ext = foto.name.split('.')[-1]
            name = f"{rad_id}.{ext}"
            file_id = GDriveHandler().create_file_in_drive(name,
                                                           foto.file,
                                                           foto.content_type,
                                                           folder_id='1ipWRq4xESIomlxPmDxIGMKLGzJRShUb_')
            if file_id:
                info_email.update({'file_id': file_id, 'img_name': name})
                check = True

        return check, info_email


class UpdateDB(PostStep):

    def proceed(self, info_email: dict, rad_id: str) -> Tuple[bool, dict]:
        log.info(f"{info_email['log_text']} ...actualizando radicados en DB con id de imagen en GDrive.")
        check = False

        rad_id: str = info_email.get('ref_id')
        file_id: str = info_email.get('file_id')
        img_name: str = info_email.get('img_name')

        rad_default = Radicacion.objects.filter(numero_radicado=rad_id).first()
        if not rad_default:
            log.info(f"{info_email['log_text']} ...no fue encontrado {rad_id=} en postgres.")
        elif isinstance(rad_default.paciente_data, dict):
            rad_default.paciente_data.update({'IMG_ID': file_id, 'IMG_NAME': img_name})
            check = self.save_rad(
                rad_default, info_email, 'actualizado radicado en postgres.'
            )
        if not DEBUG:
            rad_server = Radicacion.objects.using('server').filter(numero_radicado=rad_id).first()
            if not rad_server:
                log.info(f"{info_email['log_text']} ...no fue encontrado {rad_id=} en server.")
            elif isinstance(rad_server.paciente_data, str):
                rad_server.paciente_data = {'IMG_ID': file_id, 'IMG_NAME': img_name}
                check = self.save_rad(
                    rad_server, info_email, 'actualizado radicado en server.'
                )
        return check, info_email

    def save_rad(self, radicacion, info_email, log_msg):
        radicacion.save()
        log.info(f"{info_email['log_text']} ...{log_msg}")

        return True
