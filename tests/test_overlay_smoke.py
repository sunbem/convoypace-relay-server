"""Quick smoke test for the redesigned overlay UI."""
import sys
sys.path.insert(0, '.')
from client.config_manager import ConfigManager
from client.overlay_window import OverlayWindow

cfg = ConfigManager()
cfg.set('overlay_locked', False)
o = OverlayWindow(cfg)

mock = {
    'room_code': 'TRUCK-42',
    'route': {'source': 'Berlin', 'destination': 'Paris', 'cargo': 'Electronics'},
    'drivers': [
        {'rank': 1, 'driver_name': 'Alex', 'distance_km': 142.0, 'delta_km': 0.0, 'speed_kmh': 85.0, 'time_formatted': '1h 48m', 'status': 'DRIVING'},
        {'rank': 2, 'driver_name': cfg.get('driver_name'), 'distance_km': 146.0, 'delta_km': 4.0, 'speed_kmh': 82.0, 'time_formatted': '1h 51m', 'status': 'DRIVING'},
        {'rank': 3, 'driver_name': 'Mike', 'distance_km': 159.0, 'delta_km': 17.0, 'speed_kmh': 79.0, 'time_formatted': '2h 01m', 'status': 'DRIVING'},
        {'rank': 4, 'driver_name': 'Leo', 'distance_km': 0.0, 'delta_km': 0.0, 'speed_kmh': 0.0, 'time_formatted': '--:--', 'status': 'FINISHED', 'finished_rank': 1}
    ]
}
o.update_leaderboard(mock)
o.root.update_idletasks()

print('GEOM:', o.root.geometry())
print('TITLE:', o.lbl_title.cget('text').replace(chr(0x1F69A), 'TRUCK'))
print('ROUTE:', o.lbl_route.cget('text'))
print('ROWS:', len(o.rows_frame.winfo_children()))

o.set_network_connected(True)
print('STATUS:', o.lbl_status.cget('text'))

o.set_locked(True)
print('LOCK:', o.lbl_lock_status.cget('text'))

o.root.destroy()
print('OK - overlay rendered without errors')
