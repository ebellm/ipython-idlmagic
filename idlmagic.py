# -*- coding: utf-8 -*-
"""
===========
idlmagic
===========

Magics for interacting with IDL/GDL via pIDLy.

.. note::

  The ``pIDLy`` module needs to be installed separately and
  can be obtained using ``easy_install`` or ``pip``.

Usage
=====

``%idl``

{IDL_DOC}

``%idl_push``

{IDL_PUSH_DOC}

``%idl_pull``

{IDL_PULL_DOC}

"""

#-----------------------------------------------------------------------------
#  Copyright (C) 2013 Eric Bellm
#  Copyright (C) 2012 The IPython Development Team
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#-----------------------------------------------------------------------------

import tempfile
from glob import glob
from shutil import rmtree

import numpy as np
import pidly
from xml.dom import minidom

from IPython.core.displaypub import publish_display_data
from IPython.core.magic import (Magics, magics_class, line_magic,
                                line_cell_magic, needs_local_scope)
from IPython.testing.skipdoctest import skip_doctest
from IPython.core.magic_arguments import (
    argument, magic_arguments, parse_argstring
)
from IPython.utils.py3compat import unicode_to_str
from pexpect import ExceptionPexpect

class IDLMagicError(Exception):
    pass

_mimetypes = {'png' : 'image/png',
             'svg' : 'image/svg+xml',
             'jpg' : 'image/jpeg',
              'jpeg': 'image/jpeg'}

@magics_class
class IDLMagics(Magics):
    """A set of magics useful for interactive work with IDL via pIDLy.

    Uses IDL by default if installed; if IDL is not found, attempts to 
    fall back to GDL.
    """
    def __init__(self, shell, gdl=False):
        """
        Parameters
        ----------
        shell : IPython shell

        """
        super(IDLMagics, self).__init__(shell)
        #TODO: allow specifying path, executible on %load_ext
        try:
            self._idl = pidly.IDL()
        except ExceptionPexpect:
            try:
                # NB that pidly returns when it reads the text prompt--needs to 
                # match that of the interpreter!
                self._idl = pidly.IDL('gdl',idl_prompt='GDL>')
                print 'IDL not found, using GDL'
            except ExceptionPexpect:
                raise IDLMagicError('Neither IDL or GDL interpreters found')
        self._plot_format = 'png'

        # Allow publish_display_data to be overridden for
        # testing purposes.
        self._publish_display_data = publish_display_data

    @skip_doctest
    @line_magic
    def idl_push(self, line):
        '''
        Line-level magic that pushes a variable to IDL.

        `line` should be made up of whitespace separated variable names in the
        IPython namespace::

            In [7]: import numpy as np

           In [8]: X = np.arange(5)

            In [9]: X.mean()
            Out[9]: 2.0

            In [10]: %idl_push X

            In [11]: %idl print,mean(X)
            Out[11]: 2.00000

        '''
        inputs = line.split(' ')
        for input in inputs:
            input = unicode_to_str(input)
            self._idl.ex(input,assignment_value=self.shell.user_ns[input])


    @skip_doctest
    @line_magic
    def idl_pull(self, line):
        '''
        Line-level magic that pulls a variable from IDL.

            In [18]: %idl x = [1, 2, 3, 4] & y = 'hello'

            In [19]: %idl_pull x y

            In [20]: x
            Out[20]:
            array([ 1,  2,  3,  4], dtype=int16)

            In [21]: y
            Out[21]: array('hello', dtype='|S5')

        '''
        outputs = line.split(' ')
        for output in outputs:
            output = unicode_to_str(output)
            self.shell.push({output: self._idl.ev(output)})


    @skip_doctest
    @magic_arguments()
    @argument(
        '-i', '--input', action='append',
        help='Names of input variables to be pushed to IDL. Multiple names '
             'can be passed, separated by commas with no whitespace.'
        )
    @argument(
        '-o', '--output', action='append',
        help='Names of variables to be pulled from IDL after executing cell '
             'body. Multiple names can be passed, separated by commas with no '
             'whitespace.'
        )
    @argument(
        '-s', '--size', action='store',
        help='Pixel size of plots, "width,height". Default is "-s 600,375".'
        )

    @needs_local_scope
    @argument(
        'code',
        nargs='*',
        )
    @line_cell_magic
    def idl(self, line, cell=None, local_ns=None):
        '''
        Execute in IDL, and pull some of the results back into the
        Python namespace.

            In [9]: %idl X = [[1, 2], [3, 4]] & print, mean(X)
            Out[9]: 2.50000

        As a cell, this will run a block of IDL code, without returning any
        value::

            In [10]: %%idl
               ....: p = [-2, -1, 0, 1, 2]
               ....: print, poly(1,p)

            4.000000

        In the notebook, plots are published as the output of the cell, e.g.

        %idl plot, findgen(10)

        will create a line plot.

        Objects can be passed back and forth between IDL and IPython via the
        -i and -o flags in line::

            In [14]: Z = np.array([1, 4, 5, 10])

            In [15]: %idl -i Z print, mean(Z)
            Out[15]: 5.00000


            In [16]: %idl -o W W = Z * mean(Z)
            Out[16]: array([  5.,  20.,  25.,  50.], dtype=float32)

            In [17]: W
            Out[17]: array([  5.,  20.,  25.,  50.], dtype=float32)

        The size of output plots can be specified::

            In [18]: %%idl -s 600,800 
                ...: plot, findgen(10)

        '''
        args = parse_argstring(self.idl, line)

        # arguments 'code' in line are prepended to the cell lines
        if cell is None:
            # called as line magic
            code = ''
        else:
            # called as cell magic
            code = cell

        code = ' '.join(args.code) + code

        # if there is no local namespace then default to an empty dict
        if local_ns is None:
            local_ns = {}

        if args.input:
            for input in ','.join(args.input).split(','):
                input = unicode_to_str(input)
                try:
                    val = local_ns[input]
                except KeyError:
                    val = self.shell.user_ns[input]
                self._idl.ex(input,assignment_value=self.shell.user_ns[input])

        # generate plots in a temporary directory
        plot_dir = tempfile.mkdtemp().replace('\\', '/')
        if args.size is not None:
            size = args.size
        else:
            size = '600,375'

        plot_format = 'png'

        # adapted from http://moonlets.org/Code/plot2png.pro
        pre_call = '''
        set_plot,'Z'
        device, z_buffering=1, set_resolution = [%(size)s]
        !p.font = -1
        !p.charsize=1.2
        !p.charthick=1.2
        !p.thick=1.5

        ; ___<end_pre_call>___ 
        ''' % locals()

        post_call = '''
        ; ___<start_post_call>___ 

        ; load color table info
        tvlct, r,g,b, /get
        
        img = tvrd()
        device,/close

        outfile = '%(plot_dir)s/__ipy_idl_fig.png'
        ; Set the colors for each channel
        s = size(img)
        ii=bytarr(3,s[1],s[2])
        ii[0,*,*]=r[img]
        ii[1,*,*]=g[img]
        ii[2,*,*]=b[img]

        ; Write the PNG if the image is not blank
        if total(img) ne 0 then write_png, outfile, ii, r, g, b
        ''' % locals()

        # TODO: for speed reasons, consider requiring a plot argument?

        # allow for line continuations ('$') and comments (';')
        # drop everything after comments in a line
        uncommented_lines = [lin.split(';')[0].strip() for lin 
            in code.split('\n')]
        joined_lines = '\n'.join([lin for lin in uncommented_lines if 
            len(lin) > 0])
        # join line continuations
        final_code = joined_lines.replace('$\n',' ')

        codes = pre_call.split('\n') + final_code.split('\n') + \
            post_call.split('\n')

        text_outputs = [] 
        for code_i in codes:
            try:
                text_output_i = self._idl.ex(code_i,print_output=False,ret=True)
                if text_output_i is not None:
                    text_outputs.append(text_output_i)
            except:
                raise IDLMagicError('IDL could not complete execution.')

        text_output = "\n".join(text_outputs)

        key = 'IDLMagic.IDL'
        display_data = []

        # Publish text output
        if text_output:
            display_data.append((key, {'text/plain': text_output}))

        # Publish images (only one for now)
        images = [open(imgfile, 'rb').read() for imgfile in \
                  glob("%s/__ipy_idl_fig.png" % plot_dir)]
        rmtree(plot_dir)

        plot_mime_type = _mimetypes.get(plot_format, 'image/png')
        width, height = [int(s) for s in size.split(',')]
        for image in images:
            display_data.append((key, {plot_mime_type: image}))

        if args.output:
            for output in ','.join(args.output).split(','):
                output = unicode_to_str(output)
                self.shell.push({output: self._idl.ev(output)})

        for source, data in display_data:
            self._publish_display_data(source, data)


__doc__ = __doc__.format(
    IDL_DOC = ' '*8 + IDLMagics.idl.__doc__,
    IDL_PUSH_DOC = ' '*8 + IDLMagics.idl_push.__doc__,
    IDL_PULL_DOC = ' '*8 + IDLMagics.idl_pull.__doc__,
    )


def load_ipython_extension(ip):
    """Load the extension in IPython."""
    ip.register_magics(IDLMagics)
