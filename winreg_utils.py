import winreg


def try_read_registry_key(sub_key: str, value_name: str = None, value=None) -> bool:
    registry_keys = []
    registry_keys.append((winreg.HKEY_CURRENT_USER, "SOFTWARE\%s"))
    registry_keys.append((winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\%s"))
    registry_keys.append((winreg.HKEY_CURRENT_USER, "SOFTWARE\WOW6432Node\%s"))
    registry_keys.append((winreg.HKEY_LOCAL_MACHINE, "SOFTWARE\WOW6432Node\%s"))

    is_matched_key_found = False
    for registry_key in registry_keys:
        key = registry_key[0]
        sub_key_root = registry_key[1]
        try:
            combined_sub_key = sub_key_root % sub_key
            opened_key = winreg.OpenKey(key, combined_sub_key)
            if value_name != None and len(value) == 1:
                value[0] = winreg.QueryValueEx(opened_key, value_name)[0]
            # key is found
            is_matched_key_found = True
        except:
            pass
    return is_matched_key_found
