from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group, User

from core.settings import FIREBASE_DB as firebase_db, logger


class FireBase(BaseBackend):
    """Authenticate against the firebase project."""
    def authenticate(self, request, username=None, password=None):
        """
        Is executed after django.contrib.auth.backends.ModelBackend.
        Validates if the user exists in Firebase.
        :param request:
        :rtype request: <class 'django.core.handlers.wsgi.WSGIRequest'>
                Ex.: <WSGIRequest: POST '/login/?next=/soporte/bCkbXXCkCkkaaCmG3WioJq9pGzfc8XKmZ650_nQHYzUdZ1Ma1aCmGNNJoCJo'>
        :param username: 'foo'
        :rtype username: <class 'str'>
        :param password: 'bar123'
        :rtype password: <class 'str'>
        :return: User instance or None
        """
        usr = sign_in_user(username, password)  # True or False
        if usr and usr.get('role') == 'employee':
            try:
                lastname = ' '.join(usr['lastNames']).lower().strip()
                firstname = ' '.join(usr['names']).lower().strip()
                user = User.objects.get(username=usr['userName'])
                user.password = make_password(usr['password'])
                user.first_name = firstname
                user.last_name = lastname
                user.email = usr['email']
                user.groups.clear()
                group, created = Group.objects.get_or_create(name=usr['role'])
                group.user_set.add(user)
                user.save(using='default')
                # user.save(using='server')
            except User.DoesNotExist:
                user = User.objects.create(
                    username=usr['userName'],
                    password=make_password(usr['password']),
                    first_name=firstname,
                    last_name=lastname,
                    email=usr['email'])
                group, created = Group.objects.get_or_create(name=usr['role'])
                group.user_set.add(user)
                user.is_staff = False
                user.save(using='default')
                # user.save(using='server')
                logger.info(f"Usuario {usr['userName']} creado con éxito.")
            except Exception as e:
                logger.error(f"No fue posible actualizar "
                             f"o crear usuario {usr['userName']}: {e}")
            else:
                logger.info(f"Usuario {usr['userName']} actualizado con éxito.")
            finally:
                return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def sign_in_user(username: str, passw: str) -> dict:
    """
    Check if the user exists in firebase.
    If exists will return a dict like this

    Otherwise will return an empty dict.
    :param username:
    :param passw:
    :return:
    """
    res = {}
    for user in firebase_db.child('users').get().each():
        if user.val().get('userName') == username and user.val().get(
                'password') == passw:
            res = user.val()
            break
    return res
