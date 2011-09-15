# Copyright (c) 2008-2011 Simplistix Ltd
# See license.txt for license details.

from difflib import unified_diff
from pprint import pformat
from re import compile, MULTILINE
from testfixtures import identity, not_there
from testfixtures.resolve import resolve
from types import ClassType, GeneratorType

trailing_whitespace_re = compile('\s+$',MULTILINE)

def strip_blank_lines(text):
    result = []
    for line in text.split('\n'):
        if line and not line.isspace():
            result.append(line)
    return '\n'.join(result)

def compare(x,y,blanklines=True,trailing_whitespace=True):
    """
    Compare the two supplied arguments and raise an
    :class:`AssertionError` if they are not the same.

    The :class:`AssertionError` raised will attempt to provide
    descriptions of the differences found.

    :param blanklines: If `False`, then when comparing multi-line
                       strings, any blank lines in either argument
                       will be ignored.

    :param trailing_whitespace: If `False`, then when comparing
                                multi-line strings, trailing
                                whilespace on lines will be ignored.
    """
    # pre-processing
    if isinstance(x,GeneratorType) and isinstance(x,GeneratorType):
        x = tuple(x)
        y = tuple(y)
    if isinstance(x,basestring) and isinstance(y,basestring):
        if not trailing_whitespace:
            x = trailing_whitespace_re.sub('',x)
            y = trailing_whitespace_re.sub('',y)
        if not blanklines:
            x = strip_blank_lines(x)
            y = strip_blank_lines(y)

    # the check
    if x==y:
        return identity

    # error reporting
    message = None
    if isinstance(x,basestring) and isinstance(y,basestring):
            
        if len(x)>10 or len(y)>10:
            if '\n' in x or '\n' in y:
                message = '\n'+diff(x,y)
            else:
                message = '\n%r\n!=\n%r'%(x,y)
    elif not (blanklines and trailing_whitespace):
        raise TypeError(
            "if blanklines or trailing_whitespace are not True, only string "
            "arguments should be passed, got %r and %r" % (x,y)
            )
    elif ((isinstance(x,tuple) and isinstance(y,tuple))
          or
          (isinstance(x,list) and isinstance(y,list))):
        l_x = len(x)
        l_y = len(y)
        i = 0
        while i<l_x and i<l_y:
            if x[i]!=y[i]:
                break
            i+=1
        message = (
            'Sequence not as expected:\n\n'
            'same:\n%s\n\n'
            'first:\n%s\n\n'
            'second:\n%s')%(
            pformat(x[:i]),
            pformat(x[i:]),
            pformat(y[i:]),
            )
    elif isinstance(x,dict) and isinstance(y,dict):
        x_keys = set(x.keys())
        y_keys = set(y.keys())
        x_not_y = x_keys - y_keys
        y_not_x = y_keys - x_keys
        same = []
        diffs = []
        for key in x_keys.intersection(y_keys):
            if x[key]==y[key]:
                same.append(key)
            else:
                diffs.append('%r: %s != %s' % (
                    key,
                    pformat(x[key]),
                    pformat(y[key]),
                    ))
        lines = ['%s not as expected:' % x.__class__.__name__,'']
        if same:
            lines.extend(['same:',repr(same),''])
        if x_not_y:
            lines.append('in first but not second:')
            for key in sorted(x_not_y):
                lines.append('%r: %s' % (
                    key,
                    pformat(x[key])
                    ))
            lines.append('')
        if y_not_x:
            lines.append('in second but not first:')
            for key in sorted(y_not_x):
                lines.append('%r: %s' % (
                    key,
                    pformat(y[key])
                    ))
            lines.append('')
        if diffs:
            lines.append('values differ:')
            lines.extend(diffs)
            lines.append('')
        message = '\n'.join(lines)+'\n'
    if message is None:
        message = '%r != %r'%(x,y)
    raise AssertionError(message)
    
class Comparison:
    """
    These are used when you need to compare objects
    that do not natively support comparison. 

    :param object_or_type: The object or class from which to create the
                           :class:`Comparison`.
    
    :param attribute_dict: An optional dictionary containing attibutes
                           to place on the :class:`Comparison`.
    
    :param strict: If true, any expected attributes not present or extra
                   attributes not expected on the object involved in the
                   comparison will cause the comparison to fail.

    :param attributes: Any other keyword parameters passed will placed
                       as attributes on the :class:`Comparison`.
    """
    
    failed = None
    def __init__(self,
                 object_or_type,
                 attribute_dict=None,
                 strict=True,
                 **attributes):
        if attributes:
            if attribute_dict is None:
                attribute_dict = attributes
            else:
                attribute_dict.update(attributes)
        if isinstance(object_or_type,basestring):
            container, method, name, c = resolve(object_or_type)
            if c is not_there:
                raise AttributeError('%r could not be resolved' % object_or_type)
        elif isinstance(object_or_type,(ClassType,type)):
            c = object_or_type
        elif isinstance(object_or_type,BaseException):
            c = object_or_type.__class__
            if attribute_dict is None:
                attribute_dict = vars(object_or_type)
                attribute_dict['args']=object_or_type.args
        else:
            c = object_or_type.__class__
            if attribute_dict is None:
                attribute_dict=vars(object_or_type)
        self.c = c
        self.v = attribute_dict
        self.strict = strict
        
    def __eq__(self,other):
        if self.c is not other.__class__:
            self.failed = True
            return False
        if self.v is None:
            return True
        self.failed = {}
        if isinstance(other,BaseException):
            v = vars(other)
            v['args']=other.args
        else:
            try:
                v = vars(other)
            except TypeError:
                if self.strict:
                    raise TypeError(
                        '%r does not support vars() so cannot '
                        'do strict comparison' % other
                        )
                v = {}
                for k in self.v.keys():
                    try:
                        v[k]=getattr(other,k)
                    except AttributeError:
                        pass
        e = set(self.v.keys())
        a = set(v.keys())
        for k in e.difference(a):
            try:
                # class attribute?
                v[k]=getattr(other,k)
            except AttributeError:
                self.failed[k]='%s not in other' % repr(self.v[k])
            else:
                a.add(k)
        if self.strict:
            for k in a.difference(e):
                self.failed[k]='%s not in Comparison' % repr(v[k])
        for k in e.intersection(a):
            ev = self.v[k]
            av = v[k]
            if ev!=av:
                self.failed[k]='%r != %r' % (ev,av)
        if self.failed:
            return False
        return True

    def __ne__(self,other):
        return not(self==other)
    
    def __repr__(self,indent=2):
        full = False
        if self.failed is True:
            v = 'wrong type</C>'
        elif self.v is None:
            v = ''
        else:
            full = True
            v = '\n'
            if self.failed:
                vd = self.failed
                r = str
            else:
                vd = self.v
                r = repr
            for vk,vv in sorted(vd.items()):
                if isinstance(vv,Comparison):
                    vvr = vv.__repr__(indent+2)
                else:
                    vvr = r(vv)
                v+=(' '*indent+'%s:%s\n'%(vk,vvr))
            v+=(' '*indent)+'</C>'
        name = getattr(self.c,'__module__','')
        if name:
            name+='.'
        name += getattr(self.c,'__name__','')
        if not name:
            name = repr(self.c)
        r = '<C%s:%s>%s'%(self.failed and '(failed)' or '',name,v)
        if full:
            return '\n'+(' '*indent)+r
        else:
            return r

class StringComparison:
    """
    An object that can be used in comparisons of expected and actual
    strings where the string expected matches a pattern rather than a
    specific concrete string.

    :param regex_source: A string containing the source for a regular
                         expression that will be used whenever this
                         :class:`StringComparison` is compared with
                         any :class:`basestring` instance.
    
    """
    def __init__(self,regex_source):
        self.re = compile(regex_source)

    def __eq__(self,other):
        if not isinstance(other,basestring):
            return
        if self.re.match(other):
            return True
        return False

    def __ne__(self,other):
        return not self==other

    def __repr__(self):
        return '<S:%s>' % self.re.pattern

    def __lt__(self,other):
        return self.re.pattern<other
        
    def __gt__(self,other):
        return self.re.pattern>other
        
    def __cmp__(self,other):
        return cmp(self.re.pattern,other)
        
def diff(x,y):
    """
    A shorthand function that uses :mod:`difflib` to return a
    string representing the differences between the two string
    arguments.

    Most useful when comparing multi-line strings.
    """
    return '\n'.join(
        tuple(unified_diff(
            x.split('\n'),
            y.split('\n'),
            lineterm='')
              )[2:]
        )


