from nmigen import *
from nmigen_soc import wishbone
from lambdasoc.cpu import CPU
from urllib import request


__all__ = ["VexRiscvLinuxCPU"]


class VexRiscvLinux(Elaboratable):
    URL = "https://raw.githubusercontent.com/litex-hub/pythondata-cpu-vexriscv/master/pythondata_cpu_vexriscv/verilog/VexRiscv_Linux.v"

    def __init__(self, reset_address=0x0, domain='sync'):
        self._domain = domain

        self.ibus = wishbone.Interface(
            addr_width=30, data_width=32, granularity=8,
            features={"err", "cti", "bte"}
        )
        self.dbus = wishbone.Interface(
            addr_width=30, data_width=32, granularity=8,
            features={"err", "cti", "bte"}
        )

        self.external_interrupt = Signal(32)
        self.timer_interrupt    = Signal()
        self.software_interrupt = Signal()

        self.reset_address = reset_address

    def elaborate(self, platform):
        m = Module()
        m.submodules.cpu = Instance(
            'VexRiscv',
            i_externalResetVector = Const(self.reset_addr, 32),
            i_timerInterrupt = self.timer_interrupt,
            i_softwareInterrupt = self.software_interrupt,
            i_externalInterruptArray = self.external_interrupt,
            o_iBusWishbone_CYC = self.ibus.cyc,
            o_iBusWishbone_STB = self.ibus.stb,
            i_iBusWishbone_ACK = self.ibus.ack,
            o_iBusWishbone_WE = self.ibus.we,
            o_iBusWishbone_ADR = self.ibus.adr,
            i_iBusWishbone_DAT_MISO = self.ibus.dat_r,
            o_iBusWishbone_DAT_MOSI = self.ibus.dat_w,
            o_iBusWishbone_SEL = self.ibus.sel,
            i_iBusWishbone_ERR = self.ibus.err,
            o_iBusWishbone_CTI = self.ibus.cti,
            o_iBusWishbone_BTE = self.ibus.bte,
            o_dBusWishbone_CYC = self.dbus.cyc,
            o_dBusWishbone_STB = self.dbus.stb,
            i_dBusWishbone_ACK = self.dbus.ack,
            o_dBusWishbone_WE = self.dbus.we,
            o_dBusWishbone_ADR = self.dbus.adr,
            i_dBusWishbone_DAT_MISO = self.dbus.dat_r,
            o_dBusWishbone_DAT_MOSI = self.dbus.dat_w,
            o_dBusWishbone_SEL = self.dbus.sel,
            i_dBusWishbone_ERR = self.dbus.err,
            o_dBusWishbone_CTI = self.dbus.cti,
            o_dBusWishbone_BTE = self.dbus.bte,
            i_clk = ClockSignal(self._domain),
            i_reset = ResetSignal(self._domain),
        )

        if platform is not None:
            platform.add_file('vexriscv.v', request.urlopen(self.URL).read())
        return m

class VexRiscvLinuxCPU(CPU, VexRiscvLinux):
    name       = "vexriscv"
    arch       = "riscv"
    byteorder  = "little"
    data_width = 32

    def __init__(self, reset_address=0x0):
        super().__init__(reset_address=reset_address)
        self.ip   = Signal(32)

    @property
    def reset_addr(self):
        return self.reset_address

    @property
    def muldiv(self):
        return "hard"

    def elaborate(self, platform):
        m = super().elaborate(platform)
        m.d.comb += self.external_interrupt.eq(self.ip)
        return m
