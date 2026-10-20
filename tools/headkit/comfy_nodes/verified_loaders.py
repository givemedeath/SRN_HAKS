"""Hash-keyed wrappers for ComfyUI checkpoint loaders used by frozen requests."""
import copy

from .model_resolution import MODEL_PIN_FIELDS, STANDARD_MODEL_FIELDS, VERIFIED_LOADER_TYPES, verify_model_file


def verified_loader_mappings(core_nodes, folder_paths):
    """Wrap the installed Comfy loader implementations without duplicating them."""
    wrappers = {}
    for (original_type, model_field), category in STANDARD_MODEL_FIELDS.items():
        original = core_nodes.get(original_type)
        if original is None:
            continue
        original_inputs = original.INPUT_TYPES()
        model_field_found = any(model_field in original_inputs.get(section, {})
                                for section in ('required', 'optional'))
        if not model_field_found or not getattr(original, 'FUNCTION', None):
            continue
        wrapper_type = VERIFIED_LOADER_TYPES[original_type]

        @classmethod
        def input_types(cls, source=original_inputs):
            result = copy.deepcopy(source)
            required = result.setdefault('required', {})
            required[MODEL_PIN_FIELDS[0]] = ('STRING', {'default': ''})
            required[MODEL_PIN_FIELDS[1]] = ('STRING', {'default': ''})
            return result

        @classmethod
        def is_changed(cls, headkit_model_sha256, headkit_model_path_identity, **inputs):
            # These values enter ComfyUI's cache signature, separating same-name replacements.
            return headkit_model_path_identity + ':' + headkit_model_sha256

        def load_verified(self, headkit_model_sha256, headkit_model_path_identity,
                          _field=model_field, _category=category, _original=original,
                          _function=original.FUNCTION, **inputs):
            name = inputs.get(_field)
            verify_model_file(_category, name, headkit_model_path_identity,
                              headkit_model_sha256, folder_paths)
            return getattr(_original(), _function)(**inputs)

        attributes = {
            '__module__': __name__,
            'INPUT_TYPES': input_types,
            'IS_CHANGED': is_changed,
            'RETURN_TYPES': original.RETURN_TYPES,
            'FUNCTION': 'load_verified',
            'CATEGORY': 'srn/headkit/verified-loaders',
            'load_verified': load_verified,
        }
        for attribute in ('RETURN_NAMES', 'OUTPUT_IS_LIST', 'OUTPUT_TOOLTIPS',
                          'INPUT_IS_LIST', 'OUTPUT_NODE'):
            if hasattr(original, attribute):
                attributes[attribute] = getattr(original, attribute)
        wrappers[wrapper_type] = type(wrapper_type, (), attributes)
    return wrappers
