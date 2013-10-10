ipython-idlmagic
================

[IDL](http://www.exelisvis.com/ProductsServices/IDL.aspx)/[GDL](http://gnudatalanguage.sourceforge.net/) magics for IPython using [pIDLy](https://github.com/anthonyjsmith/pIDLy).

## Installation

At the command line, install pIDLy:

    $ pip install pidly

In IPython, install idlmagic:

    In [1]: %install_ext https://raw.github.com/ebellm/ipython-idlmagic/master/idlmagic.py
    
## Usage

In Ipython, load the magics:

    In [2]: %load_ext idlmagic
   
`idlmagic` will first look for the `idl` interpreter on the search path and fall back to `gdl` if it is not found.

### Line magics

The `%idl` magic enables one-line execution of idl commands in the IPython interpreter or notebook:

```
In [3]: %idl print, findgen(5)
      0.00000      1.00000      2.00000      3.00000      4.00000
```

### Cell magics

Multi-line input can be entered with the `%%idl` cell magic:

```
In [4]: %%idl
   ...: x = findgen(5)
   ...: y = x^2.
   ...: ; comments are supported
   ...: print, $ ; as are line continuations
   ...:     mean(y)
   ...:
% Compiled module: MEAN.
      6.00000
```

### Passing variables between Python and IDL

The mechanisms for passing variables to and from IDL are based on those in the built-in `%R` and `%octave` magics.

Variables may be pushed from Python into IDL with `%idl_push`:

```
In [5]: msg = '  padded   string   '

In [6]: import numpy as np

In [7]: arr = np.arange(5)

In [8]: %idl_push msg arr

In [9]: %%idl
   ....: print, strcompress(msg,/REMOVE_ALL)
   ....: print, reverse(arr)
   ....:
paddedstring
                     4                     3                     2
                     1                     0
```

Similarly, variables can be pulled from IDL back to Python with `%idl_pull`:

```
In [10]: %idl arr += 1

In [11]: %idl_pull arr

In [12]: arr
Out[12]: array([1, 2, 3, 4, 5])
```

Variables can also be pushed and pulled from IDL inline using the `-i` (or ``--input``) and `-o` (or `--output`) flags:

```
In [13]: Z = np.array([1, 4, 5, 10])

In [14]: %idl -i Z -o W W = sqrt(Z)

In [15]: W
Out[15]: array([ 1.        ,  2.        ,  2.23606801,  3.1622777 ], dtype=float32)
```

### Plotting

Inline plots are displayed automatically by the IPython notebook.  IDL Direct graphics are used.  The optional `-s width,height` argument (or `--size`; default: `600,375`) specifies the size of the resulting png image.

```
In [16]: %%idl -s 400,400
plot, findgen(10), xtitle='X', ytitle='Y'
```


## Known issues and limitations

* Only one plot can be rendered per cell
* Processing for possibly unused plot output slows execution
* Scalar variables from IDL may be returned as single-element Numpy arrays
* The `%idl` line magic fails with `TypeError: coercing to Unicode: need string or buffer, dict found` in IPython 0.13.2 and below due to a [known bug](http://stackoverflow.com/questions/14574434/unicode-error-with-ipython-rmagic-r-seems-to-work-but-not-r-fully); IPython 1.0 and later should work as expected.
