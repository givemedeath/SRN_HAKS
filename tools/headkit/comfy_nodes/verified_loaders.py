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

        wrappers[wrapper_type] = _verified_loader(wrapper_type, original, original_inputs,
                                                  model_field, category, folder_paths)
    return wrappers


def _verified_loader(wrapper_type, original, original_inputs, model_field, category, folder_paths):
    # Factory-local cells bind each loop iteration without unresolvable default
    # expressions, and prevent internal loader bindings becoming callable inputs.
    function_name = original.FUNCTION
    @classmethod
    def input_types(cls):
        result = copy.deepcopy(original_inputs)
        required = result.setdefault('required', {})
        required[MODEL_PIN_FIELDS[0]] = ('STRING', {'default': ''})
        required[MODEL_PIN_FIELDS[1]] = ('STRING', {'default': ''})
        return result

    @classmethod
    def is_changed(cls, headkit_model_sha256, headkit_model_path_identity, **inputs):
        # These values enter ComfyUI's cache signature, separating same-name replacements.
        return headkit_model_path_identity + ':' + headkit_model_sha256

    def load_verified(self, headkit_model_sha256, headkit_model_path_identity, **inputs):
        name = inputs.get(model_field)
        verify_model_file(category, name, headkit_model_path_identity,
                          headkit_model_sha256, folder_paths)
        return getattr(original(), function_name)(**inputs)

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
    return type(wrapper_type, (), attributes)
