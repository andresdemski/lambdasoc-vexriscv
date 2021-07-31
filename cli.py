import argparse
import importlib
import os
import shutil
from textwrap import dedent
from generate_soc import GenerateSoC
from verilator_platform import get_sim_platform


def get_platform(platform_name):
    module_name, class_name = platform_name.rsplit(":", 1)
    module = importlib.import_module(name=module_name)
    platform_class = getattr(module, class_name)
    return platform_class

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("platform", type=str, help="target platform (e.g. 'nmigen_boards.versa_ecp5_5g:VersaECP55GPlatform')")
    parser.add_argument("--cpu", choices=['minerva', 'vexriscv'], default='minerva', help="cpu type")
    parser.add_argument("--sim", action="store_true", default=False, help="Run simulation")
    parser.add_argument("--baudrate", type=int, default=9600, help="UART baudrate (default: 9600)")

    args = parser.parse_args()

    platform_class = get_platform(args.platform)
    build_dir = "build"

    if args.sim:
        print(platform_class)
        platform_class = get_sim_platform(platform_class)
        build_dir = "sim"

    platform = platform_class()
    uart_pins = platform.request("uart", 0)

    uart_divisor = int(75e6 // args.baudrate)
    if args.sim:
        uart_divisor = 5

    soc = GenerateSoC(
        args.cpu,
        reset_addr=0x00000000, clk_freq=int(75e6),
        rom_addr=0x00000000, rom_size=0x4000,
        ram_addr=0x00004000, ram_size=0x2000,
        uart_addr=0xf0000000, uart_divisor=uart_divisor, uart_pins=uart_pins,
        timer_addr=0xf0001000, timer_width=32,
        sim = args.sim,
    )

    if args.sim:
        if os.path.exists(build_dir):
            shutil.rmtree(build_dir)

    bios_dir = os.path.join(build_dir, 'bios')
    soc.build(build_dir=build_dir)
    bios = os.path.join(bios_dir, 'bios.bin')
    soc.load_fw(bios)

    if not args.sim:
        platform.build(soc, script_after_read=script_after_read, synth_opts=synth_opts, do_program=False)
    else:
        platform.run(soc)
