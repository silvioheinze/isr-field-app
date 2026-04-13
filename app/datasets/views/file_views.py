from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.conf import settings
import os
import mimetypes

from ..models import DataSet, DataGeometry, DataEntry, DataEntryFile
from .dataset_views import resolve_data_input_actor


@login_required
def file_upload_view(request, entry_id):
    """Upload files for an entry"""
    entry = get_object_or_404(DataEntry, id=entry_id)
    
    # Check if user has access to this entry's dataset
    dataset = entry.geometry.dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    if not dataset.user_has_geometry_access(request.user, entry.geometry):
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        files = request.FILES.getlist('files')
        
        if files:
            uploaded_count = 0
            for file in files:
                # Validate file type (only images)
                if file.content_type.startswith('image/'):
                    DataEntryFile.objects.create(
                        entry=entry,
                        file=file,
                        filename=file.name,
                        file_type=file.content_type,
                        file_size=file.size,
                        upload_user=request.user
                    )
                    uploaded_count += 1
                else:
                    messages.warning(request, f'File {file.name} is not an image and was skipped.')
            
            if uploaded_count > 0:
                messages.success(request, f'{uploaded_count} file(s) uploaded successfully!')
        else:
            messages.error(request, 'No files selected.')
        
        return redirect('entry_detail', entry_id=entry.id)
    
    return render(request, 'datasets/file_upload.html', {
        'entry': entry
    })


@login_required
def file_download_view(request, file_id):
    """Download a file"""
    file_obj = get_object_or_404(DataEntryFile, id=file_id)
    
    # Check if user has access to this file's dataset
    dataset = file_obj.entry.geometry.dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    if not dataset.user_has_geometry_access(request.user, file_obj.entry.geometry):
        return render(request, 'datasets/403.html', status=403)
    
    if os.path.exists(file_obj.file.path):
        with open(file_obj.file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=file_obj.file_type)
            response['Content-Disposition'] = f'attachment; filename="{file_obj.filename}"'
            return response
    else:
        raise Http404("File not found")


@login_required
def file_delete_view(request, file_id):
    """Delete a file"""
    file_obj = get_object_or_404(DataEntryFile, id=file_id)
    
    # Check if user has access to this file's dataset
    dataset = file_obj.entry.geometry.dataset
    if not dataset.can_access(request.user):
        return render(request, 'datasets/403.html', status=403)
    if not dataset.user_has_geometry_access(request.user, file_obj.entry.geometry):
        return render(request, 'datasets/403.html', status=403)
    
    if request.method == 'POST':
        filename = file_obj.filename
        entry_id = file_obj.entry_id
        file_obj.delete()
        messages.success(request, f'File "{filename}" deleted successfully!')
        return redirect('entry_detail', entry_id=entry_id)

    return render(request, 'datasets/file_delete.html', {
        'entry_file': file_obj
    })


def upload_files_view(request):
    """Upload files for a geometry (new API endpoint)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
    try:
        geometry_id = request.POST.get('geometry_id')
        if not geometry_id:
            return JsonResponse({'success': False, 'error': 'Geometry ID is required'}, status=400)
        try:
            geometry = DataGeometry.objects.get(pk=geometry_id)
        except DataGeometry.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Geometry not found'}, status=404)
        dataset = geometry.dataset
        user, vc = resolve_data_input_actor(request, dataset, require_virtual_contributor=True)
        if user is None and vc is None:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        if user is None and vc == 'pending':
            return JsonResponse({'success': False, 'error': 'Please enter your name first'}, status=403)
        if user:
            if not dataset.user_has_geometry_access(user, geometry):
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        else:
            if geometry.virtual_contributor_id != vc.id:
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)

        files = request.FILES.getlist('files')
        if not files:
            return JsonResponse({'success': False, 'error': 'No files provided'}, status=400)
        
        uploaded_files = []
        for file in files:
            # Validate file type (only images)
            if file.content_type.startswith('image/'):
                # Create or get the first entry for this geometry
                entry = geometry.entries.first()
                if not entry:
                    entry = DataEntry.objects.create(
                        geometry=geometry,
                        name=geometry.id_kurz,
                        user=user,
                        virtual_contributor=vc
                    )
                file_obj = DataEntryFile.objects.create(
                    entry=entry,
                    file=file,
                    filename=file.name,
                    file_type=file.content_type,
                    file_size=file.size,
                    upload_user=user
                )
                
                uploaded_files.append({
                    'id': file_obj.id,
                    'filename': file_obj.filename,
                    'file_type': file_obj.file_type,
                    'file_size': file_obj.file_size,
                    'upload_date': file_obj.upload_date.isoformat(),
                    'download_url': file_obj.file.url
                })
            else:
                return JsonResponse({'success': False, 'error': f'File {file.name} is not an image'}, status=400)
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully uploaded {len(uploaded_files)} files',
            'files': uploaded_files
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def geometry_files_view(request, geometry_id):
    """Get files for a specific geometry"""
    try:
        geometry = get_object_or_404(DataGeometry, pk=geometry_id)
        dataset = geometry.dataset
        user, vc = resolve_data_input_actor(request, dataset, require_virtual_contributor=True)
        if user is None and vc is None:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        if user is None and vc == 'pending':
            return JsonResponse({'success': True, 'files': []})
        if user:
            if not dataset.user_has_geometry_access(user, geometry):
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        else:
            if geometry.virtual_contributor_id != vc.id:
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        files = DataEntryFile.objects.filter(entry__geometry=geometry).order_by('-upload_date')
        
        files_data = []
        for file in files:
            files_data.append({
                'id': file.id,
                'original_name': file.filename,
                'file_size': file.file_size,
                'file_type': file.file_type,
                'description': file.description,
                'uploaded_at': file.upload_date.isoformat(),
                'download_url': file.file.url
            })
        
        return JsonResponse({
            'success': True,
            'files': files_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def delete_file_view(request, file_id):
    """Delete a file (new API endpoint)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST method allowed'}, status=405)
    try:
        file_obj = get_object_or_404(DataEntryFile, pk=file_id)
        geometry = file_obj.entry.geometry
        dataset = geometry.dataset
        user, vc = resolve_data_input_actor(request, dataset, require_virtual_contributor=True)
        if user is None and vc is None:
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        if user is None and vc == 'pending':
            return JsonResponse({'success': False, 'error': 'Please enter your name first'}, status=403)
        if user:
            if not dataset.user_has_geometry_access(user, geometry):
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        else:
            if geometry.virtual_contributor_id != vc.id:
                return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        
        filename = file_obj.filename
        file_obj.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'File "{filename}" deleted successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
