import logging
import itertools

from app.api.models.schemas import AssetRequest, BDMRequest, PPMRequest, FARequest, SBRequest, ContractRequest, EmployeeRequest
from app.api.routes.assets    import get_assets
from app.api.routes.bdm       import get_bdm
from app.api.routes.ppm       import get_ppm
from app.api.routes.fa        import get_fa
from app.api.routes.sb        import get_sb
from app.api.routes.contract  import get_contracts
from app.api.routes.employee  import get_employees
from app.api.advance.retrieval.mappings import ALL_MAPPINGS

logger = logging.getLogger("advance.retrieval.layer")


MODULE_ROUTER_MAP = {
    "assets":    (AssetRequest,    get_assets),
    "bdm":       (BDMRequest,      get_bdm),
    "ppm":       (PPMRequest,      get_ppm),
    "fa":        (FARequest,       get_fa),
    "sb":        (SBRequest,       get_sb),
    "contracts": (ContractRequest, get_contracts),
    "employees": (EmployeeRequest, get_employees),
}


def generate_permutations(filter_values: dict) -> list[dict]:
    """
    Given a dictionary of filter values where some values might be lists,
    generate a list of dictionaries representing all permutations.
    Example: 
        {'status': 'online', 'mode': ['call', 'web']}
        -> [{'status': 'online', 'mode': 'call'}, {'status': 'online', 'mode': 'web'}]
    """
    if not filter_values:
        return [{}]
        
    keys = list(filter_values.keys())
    value_lists = []
    
    for k in keys:
        v = filter_values[k]
        if isinstance(v, list):
            value_lists.append(v)
        else:
            value_lists.append([v])
            
    permutations = []
    for combo in itertools.product(*value_lists):
        permutations.append(dict(zip(keys, combo)))
        
    return permutations


def run_retrieval_layer(
    user_name: str,
    user_id: str,
    modules: list[str],
    filter_values: dict,
    filter_fields: dict,
    limit: int | None = None
) -> dict:
    """
    Executes the retrieval logic for the identified modules.
    
    - Handles list permutations in filter_values.
    - Maps frontend filter keys to backend SP parameter names.
    - Merges results across permutations.
    - Trims response fields to match filter_fields.
    
    Returns:
        dict: A mapping of module name to its retrieved data.
              e.g. {'bdm': {'p_list': [...trimmed...], 'p_count': N}}
    """
    retrieved_data = {}
    
    for module in modules:
        if module not in MODULE_ROUTER_MAP:
            logger.warning("[Retrieval Layer] Module '%s' not recognized.", module)
            continue
            
        ReqSchema, sp_func = MODULE_ROUTER_MAP[module]
        
        # 1. Get mappings for the module
        mapping_dicts = ALL_MAPPINGS.get(module)
        if mapping_dicts:
            str_map, bool_map, num_map = mapping_dicts
            all_module_mappings = {**str_map, **bool_map, **num_map}
        else:
            all_module_mappings = {}
            
        # 2. Extract values and fields for this specific module
        mod_filter_values = filter_values.get(module, {})
        mod_filter_fields = filter_fields.get(module, {})
        
        # 3. Generate permutations
        perms = generate_permutations(mod_filter_values)
        logger.info("[Retrieval Layer] Module '%s': generated %d permutations from filters.", module, len(perms))
        
        combined_p_list = []
        
        # 4. Fetch data for each permutation
        for perm in perms:
            # Base payload with defaults.
            _user_id   = user_id   if (user_id   and str(user_id).strip())   else None
            _user_name = user_name if (user_name and str(user_name).strip()) else None

            payload = {
                "user_name": _user_name,
                "user_id":   _user_id,
                "offset":    0,
                "is_aggregate": False
            }
            if limit is not None:
                payload["limit"] = limit
                
            # Map keys to backend payload schema
            for raw_key, raw_val in perm.items():
                arg_name = all_module_mappings.get(raw_key, raw_key.lower())
                payload[arg_name] = raw_val
                
            try:
                # Instantiate schema (validates/coerces types)
                req = ReqSchema(**payload)
                
                # Log the constructed payload (excluding None values for readability)
                logger.info("[Retrieval Layer] Module '%s' payload generated: %s", module, req.model_dump(exclude_none=True))
                
                # Directly invoke the route's backend SP function
                result = sp_func(req)
                p_list = result.get("p_list", [])
                combined_p_list.extend(p_list)
            except Exception as e:
                logger.error("[Retrieval Layer] Failed to retrieve data for module '%s' on permutation %s: %s", module, perm, e, exc_info=True)
                
        # 5. Trim fields (only keep what is specified in filter_fields for this module)
        if mod_filter_fields:
            logger.info("[Retrieval Layer] Module '%s': Trimming data to %d fields: %s", module, len(mod_filter_fields), list(mod_filter_fields.keys()))
            # Case-insensitive match: DB column casing can differ from filter_fields casing
            # (e.g. DB returns "wostatus" but filter_fields has "WoStatus"). Matching by exact
            # case would silently drop the column with no error, breaking every downstream
            # step that needs it. Build a lowercase lookup once per module.
            lower_to_expected = {k.lower(): k for k in mod_filter_fields}
            trimmed_list = []
            unmatched_seen: set = set()
            for row in combined_p_list:
                trimmed_row = {}
                for k, v in row.items():
                    expected_key = lower_to_expected.get(k.lower())
                    if expected_key is not None:
                        trimmed_row[expected_key] = v
                    elif k not in unmatched_seen:
                        unmatched_seen.add(k)
                trimmed_list.append(trimmed_row)
            if unmatched_seen:
                logger.warning(
                    "[Retrieval Layer] Module '%s': %d DB column(s) had no match in "
                    "filter_fields and were dropped: %s",
                    module, len(unmatched_seen), sorted(unmatched_seen),
                )
            combined_p_list = trimmed_list
        else:
            logger.info("[Retrieval Layer] Module '%s': No filter_fields provided, keeping all retrieved fields.", module)
            
        retrieved_data[module] = {
            "p_list": combined_p_list,
            "p_count": len(combined_p_list)
        }
        logger.info("[Retrieval Layer] Module '%s' retrieval complete: %d total records fetched.", module, len(combined_p_list))

    return retrieved_data
