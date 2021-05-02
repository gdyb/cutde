# noqa: F401

import logging
import os

import numpy as np

cuda_backend = False
ocl_backend = False
try:
    from .cuda import (
        cluda_preamble,
        compile,
        empty_gpu,
        threaded_get,
        to_gpu,
        zeros_gpu,
    )

    cuda_backend = True
except ImportError:
    from .opencl import (  # noqa: F401
        cluda_preamble,
        compile,
        empty_gpu,
        threaded_get,
        to_gpu,
        zeros_gpu,
    )

    ocl_backend = True

logger = logging.getLogger(__name__)

gpu_module = dict()


def np_to_c_type(t):
    if t == np.float32:
        return "float"
    elif t == np.float64:
        return "double"


def intervals(length, step_size):
    out = []
    next_start = 0
    next_end = step_size
    while next_end < length + step_size:
        this_end = min(next_end, length)
        out.append((next_start, this_end))
        next_start += step_size
        next_end += step_size
    return out


def compare(a, b):
    if type(a) != type(b):
        return False
    if type(a) is list or type(a) is tuple:
        if len(a) != len(b):
            return False
        comparisons = [compare(av, bv) for av, bv in zip(a, b)]
        if False in comparisons:
            return False
        return True
    if type(a) is np.ndarray:
        res = a == b
        if type(res) is np.ndarray:
            return res.all()
        else:
            return res
    return a == b


def get_existing_module(tmpl_name, tmpl_args):
    if tmpl_name not in gpu_module:
        return None

    existing_modules = gpu_module[tmpl_name]
    for module_info in existing_modules:
        tmpl_args_match = True
        for k, v in module_info["tmpl_args"].items():
            if not compare(v, tmpl_args[k]):
                tmpl_args_match = False
                break
        if tmpl_args_match:
            return module_info["module"]

    return None


def get_template(tmpl_name, tmpl_dir):
    import mako.lookup

    template_dirs = [os.getcwd()]
    if tmpl_dir is not None:
        template_dirs.append(tmpl_dir)
    lookup = mako.lookup.TemplateLookup(directories=template_dirs)
    return lookup.get_template(tmpl_name)


def template_with_mako(tmpl, tmpl_args):
    try:
        return tmpl.render(**tmpl_args, cluda_preamble=cluda_preamble)
    except:  # noqa: E722
        # bare except is okay because we re-raise immediately
        import mako.exceptions

        logger.error(mako.exceptions.text_error_template().render())
        raise


def load_gpu(
    tmpl_name, tmpl_dir=None, save_code=False, no_caching=False, tmpl_args=None
):
    if tmpl_args is None:
        tmpl_args = dict()

    if not no_caching and not save_code:
        existing_module = get_existing_module(tmpl_name, tmpl_args)
        if existing_module is not None:
            logger.debug("returning cached gpu module " + tmpl_name)
            return existing_module

    tmpl = get_template(tmpl_name, tmpl_dir)
    if tmpl_args is None:
        tmpl_args = dict()

    code = template_with_mako(tmpl, tmpl_args)
    with open(os.path.join(tmpl_dir, tmpl_name + ".rendered"), "w") as f:
        f.write(code)

    logger.debug("start compiling " + tmpl_name)

    module_info = dict()
    module_info["tmpl_args"] = tmpl_args
    module_info["module"] = compile(code)

    gpu_module[tmpl_name] = gpu_module.get(tmpl_name, []) + [module_info]
    return module_info["module"]
