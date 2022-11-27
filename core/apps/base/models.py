from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    IntegerField,
    Model,
)


class Municipio(Model):
    name = CharField(max_length=128)
    departamento = CharField(max_length=128)

    class Meta:
        unique_together = ('name', 'departamento')
        ordering = ['departamento', 'name']

    def __str__(self):
        return f"{self.name.title()}, {self.departamento.title()}"


class Barrio(Model):
    name = CharField(max_length=128)
    zona = CharField(max_length=20)
    municipio = ForeignKey(Municipio, on_delete=CASCADE)
    cod_zona = IntegerField()
    status = IntegerField()

    class Meta:
        unique_together = ('municipio', 'name', 'zona', 'cod_zona')
        ordering = ['cod_zona', 'name']

    def __str__(self):
        return f"{self.name.title()} - Zona {self.zona.title()}"
