# Tailscale Standalone Installer

A Python-based tool to build standalone Tailscale installers for Windows that can be deployed without requiring users to manually enter authentication keys.

## Features

- Downloads the latest Tailscale MSI automatically
- Embeds authentication key and MSI into a single executable
- Creates a standalone installer that runs with administrator privileges
- Automatically configures and starts Tailscale service
- Comprehensive logging and error handling

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Edit `.env` and add your Tailscale auth key:
     ```
     TAILSCALE_AUTH_KEY=tskey-auth-your-actual-key-here
     ```

3. **Get your Tailscale auth key:**
   - Go to [Tailscale Admin Console](https://login.tailscale.com/admin/settings/keys)
   - Create a new auth key
   - Copy the key and paste it in your `.env` file

## Usage

### Building the Installer

```bash
python src/installer_builder.py
```

This will:
1. Load the auth key from the `TAILSCALE_AUTH_KEY` environment variable
2. Download the latest Tailscale MSI
3. Create an embedded agent with the auth key and MSI
4. Build a standalone executable using PyInstaller
5. Output the installer to `builds/dist/`

### Deploying the Installer

1. Copy the generated `.exe` file to target Windows machines
2. Right-click the installer and select "Run as administrator"
3. The installer will automatically:
   - Install Tailscale
   - Configure the service
   - Authenticate with your Tailnet
   - Start the Tailscale connection

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `TAILSCALE_AUTH_KEY` | Yes | Your Tailscale authentication key |
| `TS_OAUTH_CLIENT_ID` | No | OAuth client ID for API access |
| `TS_OAUTH_CLIENT_SECRET` | No | OAuth client secret for API access |
| `TS_TAILNET` | No | Your Tailnet name |
| `BUILD_OUTPUT_DIR` | No | Output directory for builds (default: `builds`) |
| `TEMP_DIR` | No | Temporary directory (default: `temp`) |
| `LOG_LEVEL` | No | Logging level (default: `INFO`) |

## File Structure

```
tailscale-standalone/
├── src/
│   ├── installer_builder.py    # Main builder script
│   ├── config.py              # Configuration management
│   └── tailscale_api.py       # Tailscale API client
├── templates/
│   ├── agent_template.py      # Template for embedded agent
│   └── install_script.ps1     # PowerShell installation script
├── builds/                    # Generated installers
├── .env.example              # Environment variables template
├── requirements.txt          # Python dependencies
└── README.md                # This file
```

## Troubleshooting

### Build Issues

- **ModuleNotFoundError**: Make sure you're running from the project root directory
- **Auth key not found**: Ensure `TAILSCALE_AUTH_KEY` is set in your `.env` file
- **PyInstaller errors**: Try running `pip install --upgrade pyinstaller`

### Installation Issues

- **Administrator privileges required**: Always run the installer as administrator
- **Antivirus blocking**: Add the installer to antivirus exclusions
- **Network issues**: Ensure internet connectivity for Tailscale authentication

## Security Notes

- Keep your `.env` file secure and never commit it to version control
- Use ephemeral auth keys that expire after deployment
- Consider using OAuth keys for production deployments
- The generated installer contains your auth key - protect it accordingly

## License

This project is for internal use. Please ensure compliance with Tailscale's terms of service.
