import json

import os

import copy
from django.conf import settings as project_settings
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.db import IntegrityError
from django.http import Http404, HttpResponse

import xlrd
from django.utils.decorators import method_decorator
from django.views.generic import View
from django.shortcuts import render, redirect, get_object_or_404

@method_decorator(login_required, name='dispatch')
class UploadView(View):
    form = None
    model = None

    def get(self, request, *args, **kwargs):
        if args[0]:
            id = int(args[0].rstrip('/'))
            return self.view_choose_columns(request, id)

        return self.view_upload(request)

    def post(self, request, *args, **kwargs):
        if args[0]:
            id = int(args[0].rstrip('/'))
            return self.view_choose_columns(request, id)
        return self.view_upload(request)

    def view_upload(self, request):
        from tableimport.forms import UploadForm
        from tableimport.models import Upload
        form = UploadForm(request.POST or None, request.FILES or None)
        if form.is_valid():
            upload_obj = form.save(commit=False)
            upload_obj.user = request.user
            upload_obj.save()
            return redirect('./{}/'.format(upload_obj.id))
        uploads = Upload.objects.filter(user=request.user)
        return render(request, 'tableimport/upload.html', {'uploads': uploads})

    def view_choose_columns(self, request, upload_id):
        from tableimport.models import Upload, ColumnUploadError, Column
        upload = get_object_or_404(Upload, id=upload_id)
        if request.method == 'POST':
            try:
                col_nums = request.POST.getlist('col_indexes[]')
                field_choices = request.POST.getlist('field_choices[]')
                skip_first = request.POST['skip_first']
            except ValueError:
                raise Http404
            check_repited = self._check_repited(field_choices)
            if check_repited:
                return HttpResponse('You have chosen the "{}" field more than once'.format(check_repited), status=400)
            required_fields_left = self._check_required_fields(field_choices)
            if required_fields_left:
                return HttpResponse('Select the following fields, they are required{}'.format(required_fields_left),
                                    status=400)
            Column.objects.filter(upload=upload).delete()
            for x in range(len(col_nums)):
                try:
                    Column.objects.create(upload=upload, col_num=col_nums[x], field=field_choices[x])
                except IntegrityError:
                    try:
                        col = Upload.objects.get(upload=upload, col_num=col_nums[x])
                        col.delete()
                    except Upload.DoesNotExist:
                        pass
                    try:
                        col = Upload.objects.get(upload=upload, field=field_choices[x])
                        col.delete()
                    except Upload.DoesNotExist:
                        pass
                    Column.objects.create(upload=upload, col_num=col_nums[x], field=field_choices[x])
            success = self.do_import(upload, skip_first)
            upload = Upload.objects.get(pk=upload.id)
            return self.created_objects_list(request, upload,
                                             ColumnUploadError.objects.filter(upload=upload),
                                             success, skip_first)
        workbook = xlrd.open_workbook(filename=upload.file.path)
        sheet = workbook.sheet_by_index(0)
        columns = {}
        for colnum in range(sheet.ncols):
            col_values = sheet.col_values(colnum)
            if any(col_values):
                columns[colnum] = [self._try_int(val) for val in col_values[:20]]
        field_choices = self.form().fields.keys()
        return render(request, 'tableimport/choose_columns.html', {
            'upload': upload,
            'columns': columns,
            'field_choices': field_choices,
        })

    def _check_required_fields(self, post_fields):
        m_fields = self.model._meta.get_fields()
        left_fields = []
        for f in m_fields:
            if f.name == 'id':
                continue
            if hasattr(f, 'blank') and not f.blank:
                if not f.name in post_fields:
                    left_fields.append(f.name)
        return left_fields

    def _check_repited(self, post_fields):
        for field in post_fields:
            if post_fields.count(field) > 1:
                return field
        return False

    def do_import(self, upload, skip_first):
        from .models import ColumnUploadError
        self.before_import(upload)

        parsed_rows = self._parsed_rows(upload)
        ColumnUploadError.objects.filter(upload=upload).delete()

        success = []
        for ind, row in enumerate(parsed_rows):
            if ind == 0 and skip_first:
                continue

            # Validating
            errors = {}
            _row = copy.deepcopy(row)
            form = self.form(_row)
            if not form.is_valid():
                errors = form.errors.as_data()

                for key, value in errors.items():
                    errors[key] = value
            else:
                try:
                    created_object = self.on_row(upload, row)
                except Exception, e:
                    errors['non_field_errors'] = unicode(e.message)
            if errors:
                errors_to_send = {}
                for key, _errors in errors.items():
                    if key == 'non_field_errors':
                        errors_to_send[key] = unicode(errors['non_field_errors'])
                    else:
                        for error in _errors:
                            value = '\n'.join([unicode(message) for message in error.messages])
                            errors_to_send[key] = value

                json_errors = json.dumps(errors_to_send)
                json_row = json.dumps(row)

                def _rel(*x):
                    return os.path.join(*x)

                dir_path = _rel(project_settings.BASE_DIR, '..', 'files', 'upload', 'json')
                if not os.path.exists(dir_path):
                    os.makedirs(dir_path)

                json_errors_path = _rel(dir_path, 'errors.json')
                json_row_path = _rel(dir_path, 'row.json')
                with open(json_errors_path, 'w') as f:
                    f.write(json_errors)
                with open(json_row_path, 'w') as f:
                    f.write(json_row)
                c = ColumnUploadError(upload=upload, row_num=ind)
                with open(json_errors_path, 'r') as f:
                    c.errors.save('errors_json_{}'.format(upload.id), File(f), save=False)
                with open(json_row_path, 'r') as f:
                    c.row.save('row_json_{}'.format(upload.id), File(f), save=True)

            else:
                created_object = self.form._meta.model.objects.latest('id')
                created_object.row_num = ind
                success.append(created_object)
        self.after_import(upload)
        return success

    def _parsed_rows(self, upload):
        columns = upload.column_set.all()
        workbook = xlrd.open_workbook(filename=upload.file.path)
        sheet = workbook.sheet_by_index(0)
        rows = []
        for row_num in range(sheet.nrows):
            full_row = sheet.row_values(row_num)
            row = {}
            for col in columns:
                value = full_row[col.col_num]
                try:
                    value = int(float(value))
                except ValueError:
                    pass
                row[col.field] = value
            rows.append(row)
        return rows

    def _try_int(self, value):
        try:
            value = int(float(value))
        except ValueError:
            pass
        return value

    def created_objects_list(self, request, upload, errors, success, skip_first):
        skip_first = 1 if skip_first else 0
        workbook = xlrd.open_workbook(filename=upload.file.path)
        sheet = workbook.sheet_by_index(0)
        created_number = sheet.nrows - len(errors) - skip_first
        for error in errors:
            with open(error.row.path, 'r') as f:
                error.row = json.loads(f.read())
            with open(error.errors.path, 'r') as f:
                error.errors = json.loads(f.read())
        return render(request, 'tableimport/created_objects.html',
                      {'success': success,
                           'errors': errors, 'created_number': created_number, 'fields': self.form().fields.keys()})

    # Public interface:

    def before_import(self, upload):
        pass

    def on_row(self, upload, row):
        raise NotImplementedError('Please implement on_row')

    def after_import(self, upload):
        pass
