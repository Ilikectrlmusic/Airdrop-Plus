import socket
from typing import Optional

from zeroconf import IPVersion, ServiceInfo, Zeroconf


class MdnsAdvertiser:
    def __init__(self, host_label: str, port: int, ip: str):
        self.host_label = host_label.strip().lower()
        self.port = int(port)
        self.ip = ip
        self.zeroconf: Optional[Zeroconf] = None
        self.service_info: Optional[ServiceInfo] = None

    @property
    def host(self) -> str:
        return f'{self.host_label}.local'

    def start(self):
        if self.zeroconf is not None:
            return
        if self.host_label == '':
            raise ValueError('host_label 不能为空')
        address = socket.inet_aton(self.ip)
        self.zeroconf = Zeroconf(ip_version=IPVersion.V4Only)
        self.service_info = ServiceInfo(
            type_='_http._tcp.local.',
            name=f'AirDropPlus-{self.host_label}._http._tcp.local.',
            addresses=[address],
            port=self.port,
            properties={'device_id': self.host_label},
            server=f'{self.host}.',
        )
        self.zeroconf.register_service(self.service_info, allow_name_change=False)

    def stop(self):
        if self.zeroconf is None:
            return
        try:
            if self.service_info is not None:
                self.zeroconf.unregister_service(self.service_info)
        finally:
            self.zeroconf.close()
            self.zeroconf = None
            self.service_info = None
