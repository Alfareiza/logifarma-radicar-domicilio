from abc import abstractmethod, ABC

from core.apps.base.models import Radicacion
from core.apps.base.resources.email_helpers import Email
from core.apps.tasks.utils.gdrive import GDriveHandler
from core.settings import logger as log


class PostStep(ABC):

    @abstractmethod
    def proceed(self):
        ...


class NotifyEmail(PostStep, Email):
    def proceed(self, info_email: dict, rad_id: str):
        log.info(f"{info_email['log_text']} ...enviando e-mail.")
        check = False
        self.foto = info_email.get('foto', '')
        self.log_text = info_email.get('log_text')

        if self.send_mail(info_email):
            check = True
        return check, info_email


class NotifySMS(PostStep):
    def proceed(self, info_email: dict, rad_id: str):
        log.info(f"{info_email['log_text']} ...enviando SMS.")
        check = True
        # TODO Pendiente de implementar
        return check, info_email


class Drive(PostStep):
    def proceed(self, info_email: dict, rad_id: str):
        log.info(f"{info_email['log_text']} ...cargando imagen en GDrive.")
        check = False
        foto = info_email.get('foto')
        ext = foto.name.split('.')[-1]
        name = f"{rad_id}.{ext}"
        file_id = GDriveHandler().create_file_in_drive(name,
                                                       foto.file,
                                                       foto.content_type,
                                                       folder_id='1ipWRq4xESIomlxPmDxIGMKLGzJRShUb_')

        if file_id:
            check = True

        info_email.update({'file_id': file_id})
        return check, info_email


class UpdateDB(PostStep):
    def proceed(self, info_email: dict, rad_id: str):
        log.info(f"{info_email['log_text']} ...actualizando radicados en DB con id de imagen en GDrive.")
        check = False
        file_id: str = info_email.get('file_id')
        rad_default = Radicacion.objects.filter(numero_radicado=rad_id).first()
        rad_server = Radicacion.objects.using('server').filter(numero_radicado=rad_id).first()

        if rad_default and isinstance(rad_default.paciente_data, dict):
            rad_default.paciente_data.update({'FILE_ID': file_id})
            check = True
            log.info(f"{info_email['log_text']} ...actualizando radicado en postgres.")

        if rad_server and isinstance(rad_server.paciente_data, str):
            rad_server.paciente_data = {'FILE_ID': file_id}
            check = True
            log.info(f"{info_email['log_text']} ...actualizando radicado en server.")

        rad_default.save()
        rad_server.save()
        return check, info_email
