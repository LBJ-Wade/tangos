from __future__ import absolute_import
from __future__ import print_function
from pyramid.view import view_config
from pyramid.compat import escape
from sqlalchemy import func, and_, or_
import numpy as np
from . import halo_from_request, timestep_from_request, simulation_from_request
from pyramid.response import Response
import StringIO
import PIL

import tangos
import matplotlib
matplotlib.use('agg')
import pylab as p

from tangos import core

def decode_property_name(name):
    name = name.replace("_slash_","/")
    return name

def format_array(data, max_array_length=3):
    if len(data)>max_array_length:
        return "Array"
    data_fmt = []
    for d in data:
        data_fmt.append(format_data(data))
    return "["+(", ".join(data_fmt))+"]"

def format_number(data):
    if np.issubdtype(type(data), np.integer):
        return "%d" % data
    elif np.issubdtype(type(data), np.float):
        if abs(data) > 1e5 or abs(data) < 1e-2:
            return "%.2e" % data
        else:
            return "%.2f" % data

def format_data(data, request=None, relative_to=None, max_array_length=3):
    if hasattr(data,'__len__'):
        return format_array(data, max_array_length)
    elif np.issubdtype(type(data), np.number):
        return format_number(data)
    elif isinstance(data, core.Halo):
        return format_halo(data, request, relative_to)
    else:
        return escape(repr(data))



def _relative_description(this_halo, other_halo) :
    if other_halo is None :
        return "null"
    elif this_halo and this_halo.id==other_halo.id:
        return "this"
    elif this_halo and this_halo.timestep_id == other_halo.timestep_id :
        return "%s %d"%(other_halo.tag,other_halo.halo_number)
    elif this_halo and this_halo.timestep.simulation_id == other_halo.timestep.simulation_id :
        return "%s %d at t=%.2e Gyr"%(other_halo.tag,other_halo.halo_number, other_halo.timestep.time_gyr)
    else :
        if (not this_halo) or abs(this_halo.timestep.time_gyr - other_halo.timestep.time_gyr)>0.001:
            return "%s %d in %8s at t=%.2e Gyr"%(other_halo.tag,other_halo.halo_number, other_halo.timestep.simulation.basename,
                                                   other_halo.timestep.time_gyr)
        else:
            return "%s %d in %8s"%(other_halo.tag,other_halo.halo_number, other_halo.timestep.simulation.basename)


def format_halo(halo, request, relative_to=None):
    if relative_to==halo or request is None:
        return _relative_description(relative_to, halo)
    else:
        link = request.route_url('halo_view', simid=halo.timestep.simulation.basename,
                                 timestepid=halo.timestep.extension,
                                 halonumber=halo.basename)
        return "<a href='%s'>%s</a>"%(link, _relative_description(relative_to, halo))

def can_use_in_plot(data):
    return np.issubdtype(type(data), np.number)

def can_use_elements_in_plot(data_array):
    if len(data_array)==0:
        return False
    else:
        return can_use_in_plot(data_array[0])

def can_use_as_filter(data):
    return np.issubdtype(type(data), np.bool) and not np.issubdtype(type(data), np.number) and not hasattr(data,'__len__')

def can_use_elements_as_filter(data_array):
    if len(data_array)==0:
        return False
    else:
        return can_use_as_filter(data_array[0])

@view_config(route_name='gather_property', renderer='json')
def gather_property(request):
    ts = timestep_from_request(request)

    try:
        data, db_id = ts.gather_property(decode_property_name(request.matchdict['nameid']), 'dbid()')
    except Exception as e:
        return {'error': e.message, 'error_class': type(e).__name__}

    return {'timestep': ts.extension, 'data_formatted': [format_data(d, request) for d in data],
           'db_id': list(db_id), 'can_use_in_plot': can_use_elements_in_plot(data) }

@view_config(route_name='get_property', renderer='json')
def get_property(request):
    halo = halo_from_request(request)

    try:
        result = halo.calculate(decode_property_name(request.matchdict['nameid']))
    except Exception as e:
        return {'error': e.message, 'error_class': type(e).__name__}

    return {'data_formatted': format_data(result, request, halo),
            'can_use_in_plot': can_use_in_plot(result),
            'can_use_as_filter': can_use_as_filter(result)}


def start(request) :
    request.canvas =  p.get_current_fig_manager().canvas

def finish(request, getImage=True) :

    if getImage :
        request.canvas.draw()
        imageSize = request.canvas.get_width_height()
        imageRgb = request.canvas.tostring_rgb()
        buffer = StringIO.StringIO()
        pilImage = PIL.Image.frombytes("RGB",imageSize, imageRgb)
        pilImage.save(buffer, "PNG")

    p.close()

    if getImage :
        return Response(content_type='image/png',body=buffer.getvalue())


def rescale_plot(request):
    logx = request.GET.get('logx',False)
    logy = request.GET.get('logy',False)
    if logx and logy:
        p.loglog()
    elif logx:
        p.semilogx()
    elif logy:
        p.semilogy()

@view_config(route_name='gathered_plot')
def gathered_plot(request):
    ts = timestep_from_request(request)
    name1 = decode_property_name(request.matchdict['nameid1'])
    name2 = decode_property_name(request.matchdict['nameid2'])
    filter = decode_property_name(request.GET.get('filter', ""))
    object_typetag = request.matchdict.get('object_typetag',None)

    if filter!="":
        v1, v2, f = ts.gather_property(name1, name2, filter)
        v1 = v1[f]
        v2 = v2[f]
    else:
        v1, v2 = ts.gather_property(name1, name2)
    start(request)
    p.plot(v1,v2,'k.')
    p.xlabel(name1)
    p.ylabel(name2)
    rescale_plot(request)
    return finish(request)


@view_config(route_name='cascade_plot')
def cascade_plot(request):
    halo = halo_from_request(request)
    name1 = decode_property_name(request.matchdict['nameid1'])
    name2 = decode_property_name(request.matchdict['nameid2'])
    v1, v2 = halo.reverse_property_cascade(name1, name2)

    start(request)
    p.plot(v1,v2,'k')
    p.xlabel(name1)
    p.ylabel(name2)
    rescale_plot(request)
    return finish(request)




def image_plot(request, val, property_info):

    log=request.GET.get('logimage',False)
    start(request)

    width = property_info.plot_extent()
    if log:
        data = np.log10(val)
        data[data!=data]=data[data==data].min()

    else:
        data =val

    print(data.min(),data.max(),width)
    if width is not None :
        p.imshow(data,extent=(-width/2,width/2,-width/2,width/2))
    else :
        p.imshow(data)

    p.xlabel(property_info.plot_xlabel())
    p.ylabel(property_info.plot_ylabel())

    if len(val.shape) is 2 :
        cb = p.colorbar()
        if property_info.plot_clabel() :
            cb.set_label(property_info.plot_clabel())

    return finish(request)

@view_config(route_name='array_plot')
def array_plot(request):
    halo = halo_from_request(request)
    name = decode_property_name(request.matchdict['nameid'])


    val, property_info = halo.calculate(name, True)

    if len(val.shape)>1:
        return image_plot(request, val, property_info)

    start(request)

    p.plot(property_info.plot_x_values(val),val)

    if property_info.plot_xlog() and property_info.plot_ylog():
        p.loglog()
    elif property_info.plot_xlog():
        p.semilogx()
    elif property_info.plot_ylog():
        p.semilogy()

    if property_info.plot_xlabel():
        p.xlabel(property_info.plot_xlabel())

    #if property_info.plot_ylabel():
    #    p.ylabel(property_info.plot_ylabel())

    if property_info.plot_yrange():
        p.ylim(*property_info.plot_yrange())

    return finish(request)