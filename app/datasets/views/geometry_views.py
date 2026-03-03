from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.gis.geos import Point

from ..models import DataSet, DataGeometry, DataEntry, DataEntryField, DatasetField, VirtualContributor
from .dataset_views import resolve_data_input_actor


def geometry_create_view(request, dataset_id):
    """Create a new geometry point"""
    dataset = get_object_or_404(DataSet, id=dataset_id)
    user, vc = resolve_data_input_actor(request, dataset, require_virtual_contributor=True)
    if user is None and vc is None:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Access denied'}, status=403)
        return render(request, 'datasets/403.html', status=403)
    if user is None and vc == 'pending':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Please enter your name first'}, status=403)
        return render(request, 'datasets/403.html', status=403)

    if request.method == 'POST':
        # Handle AJAX requests
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                import json
                data = json.loads(request.body)
                
                id_kurz = data.get('id_kurz')
                address = data.get('address', 'New Point')
                geometry_data = data.get('geometry', {})
                
                if geometry_data.get('type') == 'Point':
                    coordinates = geometry_data.get('coordinates', [])
                    if len(coordinates) >= 2:
                        lng, lat = coordinates[0], coordinates[1]
                    else:
                        return JsonResponse({'success': False, 'error': 'Invalid coordinates'}, status=400)
                else:
                    return JsonResponse({'success': False, 'error': 'Only Point geometry is supported'}, status=400)
                
                if id_kurz and lng and lat:
                    # Create geometry point
                    geometry = DataGeometry.objects.create(
                        dataset=dataset,
                        id_kurz=id_kurz,
                        address=address,
                        geometry=Point(float(lng), float(lat)),
                        user=user,
                        virtual_contributor=vc
                    )
                    
                    return JsonResponse({
                        'success': True,
                        'geometry_id': geometry.id,
                        'id_kurz': geometry.id_kurz,
                        'address': geometry.address,
                        'message': f'Geometry point "{id_kurz}" created successfully!'
                    })
                else:
                    return JsonResponse({'success': False, 'error': 'ID, longitude, and latitude are required.'}, status=400)
                    
            except Exception as e:
                return JsonResponse({'success': False, 'error': str(e)}, status=500)
        
        # Handle regular form requests
        id_kurz = request.POST.get('id_kurz')
        address = request.POST.get('address')
        lng = request.POST.get('lng')
        lat = request.POST.get('lat')
        
        if id_kurz and lng and lat:
            try:
                geometry = DataGeometry.objects.create(
                    dataset=dataset,
                    id_kurz=id_kurz,
                    address=address or f'Unknown Address ({id_kurz})',
                    geometry=Point(float(lng), float(lat)),
                    user=user,
                    virtual_contributor=vc
                )
                
                messages.success(request, f'Geometry point "{id_kurz}" created successfully!')
                from django.urls import reverse
                if vc:
                    return redirect('dataset_data_input_anonymous', dataset_id=dataset.id, token=dataset.anonymous_access_token)
                return redirect('dataset_data_input', dataset_id=dataset.id)
            except Exception as e:
                messages.error(request, f'Error creating geometry: {str(e)}')
        else:
            messages.error(request, 'ID, longitude, and latitude are required.')
    
    return render(request, 'datasets/geometry_create.html', {
        'dataset': dataset
    })


def geometry_details_view(request, geometry_id):
    """API endpoint to get detailed data for a specific geometry point"""
    try:
        geometry = get_object_or_404(DataGeometry, pk=geometry_id)
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

        enabled_fields = DatasetField.order_fields(DatasetField.objects.filter(
            dataset=dataset,
            enabled=True
        ))
        geometry_data = {
            'id': geometry.id,
            'id_kurz': geometry.id_kurz,
            'address': geometry.address,
            'lat': geometry.geometry.y,
            'lng': geometry.geometry.x,
            'user': geometry.get_creator_display_name(),
            'entries': []
        }
        for entry in geometry.entries.all():
            entry_data = {
                'id': entry.id,
                'name': entry.name,
                'year': entry.year,
                'user': entry.get_creator_display_name()
            }
            
            # Add only enabled field values in the correct order
            for field_config in enabled_fields:
                # Find the corresponding field value for this entry
                field_value = entry.fields.filter(field_name=field_config.field_name).first()
                if field_value:
                    entry_data[field_config.field_name] = field_value.get_typed_value()
                else:
                    # Field is configured but no data exists yet
                    entry_data[field_config.field_name] = None
            
            geometry_data['entries'].append(entry_data)
        
        return JsonResponse({
            'success': True,
            'geometry': geometry_data
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
