# Table import
Helps you to provide uploading  data from excel to your users
## Getting Started

### Prerequisites
django project

### Installing

1) Include tableimport to your settings.

2) Do "python manage.py makemigations tableimport", "python manage.py migrate".

3) Create model which you want to upload and form for it.
```
# model
class Example(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
```
```
#form
class ExampleForm(forms.ModelForm):
    class Meta:
        model = Example
        fields = ['name', 'city']
```

Every not blank field of the model will be checked while uploading.
If you want to populate some field later, let it blank in model

4)Inherit UploadView, specify model and form, implement on_row method,
that should return creation of your object, you also can implement before_import and
after_import.
```
class ExampleUpload(tableimport.UploadView):
    model = Example
    form = ExampleForm

    def before_import(self, upload):
        self.user = self.request.user
        Example.objects.filter(user=self.user).delete()

    def on_row(self, upload, row):
        return Example.objects.create(user=self.user, **row)

    def after_import(self, upload):
        Example.objects.update(name='name')
```
5) include your view to urls, it has to be able to take param.
    ```url(r'^upload-excel/(.*?)$', ExampleUpload.as_view(), name='upload-excel')```

6) There are 3 templates that are used in uploading: choose_columns.html, created_object.html and upload.html.
They require jquery. You may want them or create your own.
6.1)'upload.html' should implement form of uploading excel file

6.2)choose_columns.html. It recieves 'columns' that is a dict of columns index and their data(of first twenty row) and 'field_choices', that contains fields of your model. When fields are chosen, send it via post and include the following params:
indexes e.g [1,2,5,10], corresponding field_choices e.g ['name', 'surname','email','phone'], and skip_first e.g True (that means whether you skip the first row or not)

6.3)'created_objects.html'. It recieves all fields of your form in 'fields', 'success' - list of model objects, and 'errors' - list of dicts of errors per object
