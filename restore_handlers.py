backup = open('static/script_backup.js', encoding='utf-8').read()
lines = backup.split('\n')
start = None
end = None
for i, line in enumerate(lines):
    if 'const firmwareProgress' in line and start is None:
        start = i
    if start and 'initFirmwareMismatchWatcher' in line:
        end = i
        break

if start and end:
    block = '\n'.join(lines[start:end]).rstrip('\n')
    current = open('static/script.js', encoding='utf-8').read()
    inject_marker = (
        'const btnUploadFirmware = document.getElementById("btn-upload-firmware");\n'
        'const firmwareModal = document.getElementById("firmware-modal");\n'
        'const closeFirmware = document.getElementById("close-firmware");\n'
        'const btnStartUpload = document.getElementById("btn-start-upload");\n'
    )
    if inject_marker in current:
        new_content = current.replace(inject_marker, inject_marker + block + '\n')
        open('static/script.js', 'w', encoding='utf-8').write(new_content)
        print('OK: Firmware handlers restored.')
    else:
        print('ERROR: Marker not found. Trying alternate...')
        # Try with just one marker line
        alt = 'const btnStartUpload = document.getElementById("btn-start-upload");\n(function initFirmwareMismatchWatcher'
        if alt in current:
            new_content = current.replace(
                'const btnStartUpload = document.getElementById("btn-start-upload");\n(function initFirmwareMismatchWatcher',
                'const btnStartUpload = document.getElementById("btn-start-upload");\n' + block + '\n(function initFirmwareMismatchWatcher'
            )
            open('static/script.js', 'w', encoding='utf-8').write(new_content)
            print('OK: Inserted via alt marker.')
        else:
            print('ERROR: No marker found.')
else:
    print(f'ERROR: Block not found start={start} end={end}')
