#!/usr/bin/env python3

with open('src/windows_installer_builder.py', 'r') as f:
    lines = f.readlines()

# Fix the merged lines
lines[1236] = '        return agent_code\n'
lines[1237] = '    \n'
lines[1238] = '    def build_standalone_installer(self):\n'
lines[1239] = '        """Build the installer"""\n'
lines[1240] = '        \n'
lines[1241] = '        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")\n'
lines[1242] = '        name = f"TailscaleInstaller-{timestamp}"\n'

with open('src/windows_installer_builder.py', 'w') as f:
    f.writelines(lines)

print('Fixed merged lines')
