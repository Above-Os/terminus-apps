#### Default credentials
Username: admin 
Password: password
Please change username and password as soon as possible.

#### Sync Setup Guide
1. Install Obsidian LiveSync on Terminus and Obsidian Client on you computer or cellphone.

2. Install and Enable Sync Plugin on Primary Device
    - Open Obsidian Client, in Vault-> Settings-> Community Plugins, Click 'Turn on Community Plugins'.
    - Then click Browse, search "Self-hosted LiveSync" and install it.
    - Enable this plugin at Settings-> Community Plugins

    <p style="display: flex; justify-content: center;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/turn_on_community_plugins.webp" alt="turn_on_community_plugins" style="max-width: 40%; height: auto; margin-right: 20px;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/livesync.webp" alt="livesync"  style="max-width: 40%; height: auto;">
    </p>

3. Set Up Remote Database.
    - Log into Obsidian LiveSync on Terminus using default credentials to get the app URL (e.g., https://8591294e.YOUR_TERMINUS_NAME.snowinning.com) and configuration information.
    - Change your admin password.
    
      ![change_password](https://file.bttcdn.com/appstore/obsidian/readme/change_password.webp)
    
    - Reopen your Obsidian Client. Navigate to Self-hosted LiveSync -> Remote Database, and input your configuration information obtained from Obsidian LiveSync on Terminus.

      ![remote_database](https://file.bttcdn.com/appstore/obsidian/readme/remote_database.webp)    
    - The database name must contain only lowercase alphabetic characters.

4. Setup the Subsequent Device
    - Install and enable "Self-hosted LiveSync" in the same way as on the primary device.
    - In Self-hosted LiveSync->Setup wizard, use Open setup URI. Paste the setup URI from Primary Device (you can get it by clicking the 'Copy setup URI' button on the same page at primary device)
    - If you enable 'End to End Encryption', use Passphrase instead of URI
    
    <p style="display: flex; justify-content: center;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/copy_uri.webp" alt="copy_uri" style="max-width: 55%; height: auto; margin-right: 5px;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/paste_uri.webp" alt="paste_uri" style="max-width: 20%; height: auto; margin-right: 5px;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/past-passphrase.png" alt="past-passphrase"  style="max-width: 20%; height: auto;">
    </p>
    
    - Import the configuration and select 'Set it up as a secondary or subsequent device' in the following dialog.

    <p style="display: flex; justify-content: center;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/import_config.png" alt="import_config" style="max-width: 20%; height: auto; margin-right: 5px;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/comfirm_setup.png" alt="comfirm_setup"  style="max-width: 20%; height: auto;">
    </p>

5. Start Sync 
    - Open realtime live sync on both device at Setting-> Community Plugin-> Self-hosted LiveSync->Sync Setting-> LiveSync
    - Enjoy LiveSync!

    <p style="display: flex; justify-content: center;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/realtime_sync1.png" alt="realtime_sync1" style="max-width: 70%; height: auto; margin-right: 5px;">
    <img src="https://file.bttcdn.com/appstore/obsidian/readme/realtime_sync2.jpg" alt="realtime_sync2"  style="max-width: 25%; height: auto;">
    </p>
