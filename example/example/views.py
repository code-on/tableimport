import tableimport
from example.forms import ExampleForm
from example.models import Example


class ExampleUpload(tableimport.UploadView):
    model = Example
    form = ExampleForm

    def before_import(self, upload):
        self.user = self.request.user
        Example.objects.filter(user=self.user).delete()

    def on_row(self, upload, row):
        return Example.objects.create(user=self.user, **row)

    def after_import(self, upload):
        try:
            Example.objects.first().update(name='first')
        except:
            pass
