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

class IDLMagicError(Exception):
    pass

_mimetypes = {'png' : 'image/png',
             'svg' : 'image/svg+xml',
             'jpg' : 'image/jpeg',
              'jpeg': 'image/jpeg'}

@magics_class
class IDLMagics(Magics):
    """A set of magics useful for interactive work with IDL via pIDLy.
    """
    def __init__(self, shell):
        """
        Parameters
        ----------
        shell : IPython shell

        """
        super(IDLMagics, self).__init__(shell)
        #TODO: allow specifying path on %load_ext
        #self._idl = pidly.IDL()
        # NB that pidly returns when it reads the text prompt--needs to 
        # match that of the interpreter!
        self._idl = pidly.IDL('gdl',idl_prompt='GDL>')
        self._plot_format = 'png'

        # Allow publish_display_data to be overridden for
        # testing purposes.
        self._publish_display_data = publish_display_data

    @skip_doctest
    @line_magic
    def idl_push(self, line):
        '''
        Line-level magic that pushes a variable to Octave.

        `line` should be made up of whitespace separated variable names in the
        IPython namespace::

            In [7]: import numpy as np

            In [8]: X = np.arange(5)

            In [9]: X.mean()
            Out[9]: 2.0

            In [10]: %idl_push X

            In [11]: %idl mean(X)
            Out[11]: 2.0

        '''
        inputs = line.split(' ')
        for input in inputs:
            input = unicode_to_str(input)
            self._idl.ex(input,assignment_value=self.shell.user_ns[input])


    @skip_doctest
    @line_magic
    def idl_pull(self, line):
        '''
        Line-level magic that pulls a variable from Octave.

            In [18]: _ = %idl x = [1, 2, 3, 4]; y = 'hello'

            In [19]: %idl_pull x y

            In [20]: x
            Out[20]:
            array([[ 1.,  2.],
                   [ 3.,  4.]])

            In [21]: y
            Out[21]: 'hello'

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
        help='Pixel size of plots, "width,height". Default is "-s 400,250".'
        )
    @argument(
        '-f', '--format', action='store',
        help='Plot format (png, svg or jpg).'
        )

    @needs_local_scope
    @argument(
        'code',
        nargs='*',
        )
    @line_cell_magic
    def idl(self, line, cell=None, local_ns=None):
        '''
        Execute in Octave, and pull some of the results back into the
        Python namespace.

            In [9]: %octave X = [1 2; 3 4]; mean(X)
            Out[9]: array([[ 2., 3.]])

        As a cell, this will run a block of Octave code, without returning any
        value::

            In [10]: %%octave
               ....: p = [-2, -1, 0, 1, 2]
               ....: polyout(p, 'x')

            -2*x^4 - 1*x^3 + 0*x^2 + 1*x^1 + 2

        In the notebook, plots are published as the output of the cell, e.g.

        %octave plot([1 2 3], [4 5 6])

        will create a line plot.

        Objects can be passed back and forth between Octave and IPython via the
        -i and -o flags in line::

            In [14]: Z = np.array([1, 4, 5, 10])

            In [15]: %octave -i Z mean(Z)
            Out[15]: array([ 5.])


            In [16]: %octave -o W W = Z * mean(Z)
            Out[16]: array([  5.,  20.,  25.,  50.])

            In [17]: W
            Out[17]: array([  5.,  20.,  25.,  50.])

        The size and format of output plots can be specified::

            In [18]: %%octave -s 600,800 -f svg
                ...: plot([1, 2, 3]);

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
            size = '400,250'

        if args.format is not None:
            plot_format = args.format
        else:
            plot_format = 'png'

        # adapted from http://moonlets.org/Code/plot2png.pro
        pre_call = '''
        set_plot,'Z'
        ;device, z_buffering=1, set_resolution = [%(size)s], decomposed=1
        device, z_buffering=1, set_resolution = [%(size)s]
        !p.font = -1
        !p.charsize=1.2
        !p.charthick=1.2
        !p.thick=1.5
        !p.color = 0
        !p.background = 256

        ; ___<end_pre_call>___ 
        ''' % locals()

        post_call = '''
        ; ___<start_post_call>___ 

        ; load color table info
        tvlct, r,g,b, /get
        
        img = tvrd()
        device,/close

        ;outfile = '%(plot_dir)s/__ipy_idl_fig_%%03d.png', f);
        outfile = '%(plot_dir)s/__ipy_idl_fig.png'
        ; Set the colors for each channel
        s = size(img)
        ii=bytarr(3,s[1],s[2])
        ii[0,*,*]=r[img]
        ii[1,*,*]=g[img]
        ii[2,*,*]=b[img]

        ; Write the PNG
        ; don't write if the image is blank
        if total(img) ne 0 then write_png, outfile, ii, r, g, b
        ''' % locals()

        #code = ''.join((pre_call, code, post_call))
        #print code
        #codes = [pre_call, code, post_call]
		# TODO: need to cut out comments, join continued lines
		# TODO: for speed reasons, consider requiring a plot argument?
        codes = pre_call.split('\n') + code.split('\n') + post_call.split('\n')

        text_outputs = [] 
        # next step is to split user code into lines to get all text?
        for code_i in codes:
            #print '> ', code_i
            #try:
            text_output_i = self._idl.ex(code_i,print_output=False,ret=True)
            #print '    ',text_output_i
            if text_output_i is not None:
                text_outputs.append(text_output_i)
            #except:
            #    raise IDLMagicError('IDL could not complete execution.')

        text_output = "\n".join(text_outputs)

        key = 'IDLMagic.IDL'
        display_data = []

        # Publish text output
        if text_output:
            display_data.append((key, {'text/plain': text_output}))

        # Publish images
        #images = [open(imgfile, 'rb').read() for imgfile in \
        #          glob("%s/*.png" % plot_dir)]
        #images = [open(imgfile, 'rb').read() for imgfile in \
        #          ["%s/__ipy_idl_fig.png" % plot_dir]]
        images = []
        #rmtree(plot_dir)

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
