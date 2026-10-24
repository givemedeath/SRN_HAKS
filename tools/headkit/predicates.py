"""JSON selection predicates shared by texture and mesh stages: all/any/not, named regions, masks, channels and
{of, center?, gt/lt/ge/le} comparisons over lazily computed named arrays."""
import numpy as np
from .common import require

COMPARE={'gt':np.greater,'lt':np.less,'ge':np.greater_equal,'le':np.less_equal}


class Values(dict):
    """Named arrays of one shape (texels or faces), computed on first use."""
    def __init__(self, factories):super().__init__();self.factories=factories
    def __missing__(self, key):
        require(key in self.factories,'Unavailable condition quantity: '+str(key))
        self[key]=value=self.factories[key]();return value


def when(condition, values, regions, depth=0):
    """JSON predicate: all/any/not, region (named), mask (paint output), channel, mapped, or {of, center?, gt/lt/ge/le}."""
    require(isinstance(condition,dict) and condition and depth<32,'Condition must be a non-empty object')
    keys=set(condition)
    for key in ('all','any'):
        if key in keys:
            require(keys=={key} and isinstance(condition[key],list) and condition[key],'Non-empty '+key+' list required')
            parts=[when(row,values,regions,depth+1) for row in condition[key]]
            return np.logical_and.reduce(parts) if key=='all' else np.logical_or.reduce(parts)
    if 'not' in keys:require(keys=={'not'},'Bare not required');return ~when(condition['not'],values,regions,depth+1)
    if 'region' in keys:
        require(keys=={'region'} and condition['region'] in regions,'Unknown region: '+str(condition['region']))
        return when(regions[condition['region']],values,regions,depth+1)
    if 'mask' in keys:require(keys=={'mask'},'Bare mask required');return values['mask:'+str(condition['mask'])]
    if 'channel' in keys:
        require(keys=={'channel'} and type(condition['channel']) is int and 0<=condition['channel']<=9,'Channel 0..9 required')
        return values['channel']==condition['channel']
    if 'mapped' in keys:
        require(keys=={'mapped'} and type(condition['mapped']) is bool,'Boolean mapped required')
        return values['mapped'] if condition['mapped'] else ~values['mapped']
    bounds=keys-{'of','center'}
    require('of' in keys and bounds and bounds<=set(COMPARE),'Comparison needs of plus gt/lt/ge/le')
    value=values[condition['of']]
    if 'center' in keys:value=np.abs(value-float(condition['center']))
    result=np.ones(value.shape,bool)
    for key in bounds:
        require(type(condition[key]) in (int,float),'Numeric bound required');result&=COMPARE[key](value,condition[key])
    return result
