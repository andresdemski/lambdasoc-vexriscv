import os
import subprocess
from nmigen import *
from nmigen_soc import wishbone

from vexriscv import VexRiscvLinuxCPU
from lambdasoc.cpu.minerva import MinervaCPU
from lambdasoc.periph.intc import GenericInterruptController
from lambdasoc.periph.serial import AsyncSerialPeripheral
from lambdasoc.periph.sram import SRAMPeripheral
from lambdasoc.periph.timer import TimerPeripheral
from lambdasoc.soc.cpu import CPUSoC


__all__ = ["SRAMSoC"]

class Pll(Elaboratable):
    def __init__(self, clk_input, o_domain='sync'):
        self.clk = clk_input
        self.lock = Signal()
        self.o_domain = o_domain

    def elaborate(self, platform):
        m = Module()
        clko = Signal()
        platform.add_clock_constraint(clko, 75e6)
        m.d.comb += ClockSignal(self.o_domain).eq(clko)

        m.submodules.pll_inst = Instance(
            'EHXPLLL',
            a_FREQUENCY_PIN_CLKI = "100",
            a_FREQUENCY_PIN_CLKOP = "75",
            a_ICP_CURRENT = "12",
            a_LPF_RESISTOR = "8",
            a_MFG_ENABLE_FILTEROPAMP = "1",
            a_MFG_GMCREF_SEL = "2",
            p_PLLRST_ENA = "DISABLED",
            p_INTFB_WAKE = "DISABLED",
            p_STDBY_ENABLE = "DISABLED",
            p_DPHASE_SOURCE = "DISABLED",
            p_OUTDIVIDER_MUXA = "DIVA",
            p_OUTDIVIDER_MUXB = "DIVB",
            p_OUTDIVIDER_MUXC = "DIVC",
            p_OUTDIVIDER_MUXD = "DIVD",
            p_CLKI_DIV = 4,
            p_CLKOP_ENABLE = "ENABLED",
            p_CLKOP_DIV = 8,
            p_CLKOP_CPHASE = 4,
            p_CLKOP_FPHASE = 0,
            p_FEEDBK_PATH = "CLKOP",
            p_CLKFB_DIV = 3,

            i_RST = Const(0, 1),
            i_STDBY = Const(0, 1),
            i_CLKI = self.clk,
            o_CLKOP = clko,
            o_CLKFB = clko,
            i_PHASESEL0 = Const(0, 1),
            i_PHASESEL1 = Const(0, 1),
            i_PHASEDIR = Const(1, 1),
            i_PHASESTEP = Const(1, 1),
            i_PHASELOADREG = Const(1, 1),
            i_PLLWAKESYNC = Const(0, 1),
            i_ENCLKOP = Const(0, 1),
            o_LOCK = self.lock,
        )
        return m

class GenerateSoC(CPUSoC, Elaboratable):
    SUPPORTED_CPUS = {
        'minerva': MinervaCPU,
        'vexriscv': VexRiscvLinuxCPU
    }

    def __init__(self, cpu, *, reset_addr, clk_freq,
                 rom_addr, rom_size,
                 ram_addr, ram_size,
                 uart_addr, uart_divisor, uart_pins,
                 timer_addr, timer_width,
                 sim=False,
                 ):
        assert cpu in self.SUPPORTED_CPUS
        assert clk_freq == int(75e6), 'Different frequency is not currently supported'

        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8,
                                         features={"cti", "bte"})


        self.cpu = self.SUPPORTED_CPUS[cpu](reset_address=reset_addr)
        self._arbiter.add(self.cpu.ibus)
        self._arbiter.add(self.cpu.dbus)

        self.rom = SRAMPeripheral(size=rom_size, writable=False)
        self._decoder.add(self.rom.bus, addr=rom_addr)

        self.ram = SRAMPeripheral(size=ram_size)
        self._decoder.add(self.ram.bus, addr=ram_addr)

        self.uart = AsyncSerialPeripheral(divisor=uart_divisor, pins=uart_pins)
        self._decoder.add(self.uart.bus, addr=uart_addr)

        self.timer = TimerPeripheral(width=timer_width)
        self._decoder.add(self.timer.bus, addr=timer_addr)

        self.intc = GenericInterruptController(width=len(self.cpu.ip))
        self.intc.add_irq(self.timer.irq, 0)
        self.intc.add_irq(self.uart .irq, 1)

        self.memory_map = self._decoder.bus.memory_map

        self.clk_freq = clk_freq
        self._sim = sim

    def load_fw(self, bin_filename):
        with open(bin_filename, "rb") as f:
            words = iter(lambda: f.read(self.cpu.data_width // 8), b'')
            fw  = [int.from_bytes(w, self.cpu.byteorder) for w in words]
        self.rom.init = fw


    def elaborate(self, platform):
        m = Module()

        clk = platform.request(platform.default_clk)
        reset  = platform.request(platform.default_rst)
        m.domains += ClockDomain('sync')

        if self._sim:
            m.d.comb += [
                ClockSignal('sync').eq(clk),
                ResetSignal('sync').eq(reset),
            ]
            platform.add_file('io.v', """
                module OB (input wire I, output wire O);
                    assign O = I;
                endmodule

                module IB (input wire I, output wire O);
                    assign O = I;
                endmodule
            """)
        else:
            m.submodules.pll = pll = Pll(clk, 'sync')
            m.d.comb += ResetSignal('sync').eq(~pll.lock),

        m.submodules.arbiter = self._arbiter
        m.submodules.cpu     = self.cpu

        m.submodules.decoder = self._decoder
        m.submodules.rom     = self.rom
        m.submodules.ram     = self.ram
        m.submodules.uart    = self.uart
        m.submodules.timer   = self.timer
        m.submodules.intc    = self.intc

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
            self.cpu.ip.eq(self.intc.ip),
        ]


        return m
