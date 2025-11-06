"""
energy_calculations.py

Abstract calculation functions for different building systems and energy efficiency measures.
Each function contains a detailed docstring explaining the purpose and formula.

Functional requirements:
- Implemented as standalone functions (not class methods).
- Use clear variable names.
- Keep formulas as close to the specification as possible.
"""

from typing import List


# -------------------------
# 1. Overall Building Performance
# -------------------------
def potential_energy_saving_building(baseline_eui: float, benchmark_eui: float, gfa: float) -> float:
    """
    Calculate the potential energy saving of the building.

    Formula:
    Potential Energy Saving of the building = (Baseline Building EUI - Benchmark Building EUI) × Building Gross Floor Area (GFA)

    :param baseline_eui: Baseline Building Energy Use Intensity (kWh/m²/year)
    :param benchmark_eui: Benchmark Building Energy Use Intensity (kWh/m²/year)
    :param gfa: Gross Floor Area of the building (m²)
    :return: Potential energy saving (kWh/year)
    """
    return (baseline_eui - benchmark_eui) * gfa


# -------------------------
# 2. Energy savings for Chiller
# -------------------------
def potential_energy_saving_chiller_replace(total_cooling_load: float, baseline_efficiency: float,
                                            benchmark_efficiency: float, operating_hours: float) -> float:
    """
    Measure #1 – Replace with More Efficient Equipment.

    Formula:
    Potential Energy Saving = Total Cooling Load × (Baseline Air Cooled/Water cooled Efficiency - Benchmark Efficiency) × Operating Hours
    """
    return total_cooling_load * (baseline_efficiency - benchmark_efficiency) * operating_hours


def potential_energy_saving_chiller_vsd(baseline_efficiency: float, total_cooling_load: float, operating_hours: float,
                                        avg_savings_percent: float) -> float:
    """
    Measure #2A – Installation of VSD.

    Formula:
    Potential Energy Saving (Option A) = Baseline Cooling Efficiency × Total Cooling Load × Operating Hours × Average Energy Savings from Installing VSD in %
    """
    return baseline_efficiency * total_cooling_load * operating_hours * (avg_savings_percent / 100.0)


def potential_energy_saving_chiller_heat_recovery(baseline_efficiency: float, total_cooling_load: float,
                                                  operating_hours: float, avg_savings_percent: float) -> float:
    """
    Measure #2B – Installation of Heat Recovery.

    Formula:
    Potential Energy Saving (Option B) = Baseline Cooling Efficiency × Total Cooling Load × Operating Hours × Average Energy Savings from Installing Heat Recovery System in %
    """
    return baseline_efficiency * total_cooling_load * operating_hours * (avg_savings_percent / 100.0)


# -------------------------
# 3. Energy savings for Split Unit/VRV
# -------------------------
def potential_energy_saving_split_vrv(total_cooling_load: float, baseline_efficiency: float,
                                      benchmark_efficiency: float, operating_hours: float) -> float:
    """
    Measure #1 – Replace with More Efficient Equipment.

    Formula:
    Potential Energy Saving = Total Cooling Load × (Baseline Air Cooled/Water cooled Efficiency - Benchmark Efficiency) × Operating Hours
    """
    return total_cooling_load * (baseline_efficiency - benchmark_efficiency) * operating_hours


# -------------------------
# 4. Energy savings for Ventilation System
# -------------------------
def potential_energy_saving_ventilation_replace(baseline_efficiency: float, benchmark_efficiency: float,
                                                operating_hours: float) -> float:
    """
    Measure #1 – Replace with More Efficient Equipment.

    Formula:
    Potential Energy Saving = (Baseline Ventilation System Efficiency - Benchmark Ventilation System Efficiency) × Operating Hours
    """
    return (baseline_efficiency - benchmark_efficiency) * operating_hours


def potential_energy_saving_ventilation_vsd(total_power_input: float, operating_hours: float,
                                            avg_savings_percent: float) -> float:
    """
    Measure #2A – Installation of VSD.

    Formula:
    Potential Energy Saving (Option A) = Total Mechanical Ventilation System Power Input × Operating Hours × Average Energy Savings from Installing VSD in %
    """
    return total_power_input * operating_hours * (avg_savings_percent / 100.0)


def potential_energy_saving_ventilation_dcv(total_power_input: float, operating_hours: float,
                                            avg_savings_percent: float) -> float:
    """
    Measure #2B – Installation of Sensors for Demand Controlled Ventilation (DCV).

    Formula:
    Potential Energy Saving (Option B) = Total Mechanical Ventilation System Power Input × Operating Hours × Average Energy Savings from Installing DCV Sensors in %
    """
    return total_power_input * operating_hours * (avg_savings_percent / 100.0)


# -------------------------
# 5. Lighting System
# -------------------------
def baseline_lpd_value(total_power_input: float, total_room_area: float) -> float:
    """
    Baseline LPD Value of specific Room Type.

    Formula:
    Baseline LPD Value = Total Power Input of Different Type of Light Bulbs in a Specific Room / Total Room Area of Specific Room Type
    """
    return total_power_input / total_room_area


def potential_energy_saving_lighting_replace(room_areas: List[float], baseline_lpd: float, benchmark_lpd: float,
                                             operating_hours: float) -> float:
    """
    Measure #1 – Replace with More Efficient Equipment.

    Formula:
    Potential Energy Saving = Σ (Total Room Area × ((Baseline LPD Value - Benchmark LPD Value) × Operating Hours)) / 1000
    """
    return sum(area * (baseline_lpd - benchmark_lpd) * operating_hours for area in room_areas) / 1000.0


def potential_energy_saving_lighting_sensors(total_power_input: float, building_operating_hours: float,
                                             avg_savings_percent: float) -> float:
    """
    Measure #2 – Adopt other energy efficiency measures (Sensors).

    Formula:
    Potential Energy Saving = Annual Lighting System Energy Consumption × Average Energy Savings from Installing Sensors in %

    Annual Lighting System Energy Consumption = Total Power Input of Lighting System × Building Operating Hours
    """
    annual_consumption = total_power_input * building_operating_hours
    return annual_consumption * (avg_savings_percent / 100.0)


# -------------------------
# 6. Lift and Escalator System
# -------------------------
def annual_lift_energy_consumption(total_annual_building_consumption: float) -> float:
    """
    Annual Lift System Energy Consumption.

    Formula:
    Annual Lift System Energy Consumption = Total Annual Building Electricity Consumption × 7.5%
    """
    return total_annual_building_consumption * 0.075


def potential_energy_saving_lift_regenerative(total_annual_building_consumption: float,
                                              avg_savings_percent: float) -> float:
    """
    Measure #2A – Installation of Regenerative Feature.

    Formula:
    Potential Energy Saving = Annual Lift System Energy Consumption × Average Energy Savings from Installing Regenerative Feature in %
    """
    return annual_lift_energy_consumption(total_annual_building_consumption) * (avg_savings_percent / 100.0)


def potential_energy_saving_lift_vvvf(total_annual_building_consumption: float, avg_savings_percent: float) -> float:
    """
    Measure #2B – Installation of VVVF Drive and Sleep Mode.

    Formula:
    Potential Energy Saving = Annual Lift System Energy Consumption × Average Energy Savings from Installing VVVF Drive and Sleep Mode in %
    """
    return annual_lift_energy_consumption(total_annual_building_consumption) * (avg_savings_percent / 100.0)


# -------------------------
# 7. Hot Water System
# -------------------------
def potential_energy_saving_hotwater_replace(baseline_efficiency: float, benchmark_efficiency: float,
                                             operating_hours: float) -> float:
    """
    Measure #1 – Replace with More Efficient Equipment.

    Formula:
    Potential Energy Saving = (Baseline System Efficiency - Benchmark System Efficiency) × Hot Water System Operating Hours
    """
    return (baseline_efficiency - benchmark_efficiency) * operating_hours


def potential_energy_saving_hotwater_heat_recovery(baseline_efficiency: float, operating_hours: float,
                                                   avg_savings_percent: float) -> float:
    """
    Measure #2 – Install Heat Recovery.

    Formula:
    Annual Energy Consumption = Baseline System Efficiency × System Operating Hours
    Potential Energy Saving = Annual Energy Consumption × Average Energy Savings from Installing Heat Recovery System in %
    """
    annual_consumption = baseline_efficiency * operating_hours
    return annual_consumption * (avg_savings_percent / 100.0)


# -------------------------
# 8. Smart Building System
# -------------------------
def potential_energy_saving_smart_system(total_annual_consumption: float, avg_savings_percent: float) -> float:
    """
    Measure #2 – Smart Building System.

    Formula:
    Potential Energy Saving = Total Annual Building Energy Consumption × Average Energy Savings from Installing Smart Systems in %
    """
    return total_annual_consumption * (avg_savings_percent / 100.0)


# -------------------------
# 9. Renewable Energy System
# -------------------------
def potential_energy_saving_renewable(total_annual_consumption: float, renewable_percent: float) -> float:
    """
    Installation of Renewable Energy Source such as Rooftop Solar.

    Formula:
    Potential Energy Saving = Total Annual Building Energy Consumption × % of Total Annual Energy Consumption Produced from Renewable Sources (Benchmark Value)
    """
    return total_annual_consumption * (renewable_percent / 100.0)


# -------------------------
# 10. Carbon Emission Reduction Calculator
# -------------------------
def avoided_emission_refrigerants(total_quantities: List[float], baseline_leakage: float,
                                  baseline_emission_factor: float, benchmark_leakage: float,
                                  benchmark_emission_factor: float) -> float:
    """
    Total Avoided Scope 1 Emission from Refrigerants.

    Formula:
    Σ (Total Refrigerant Quantity × Baseline Leakage Factor × Baseline Emission Factor)
      - Σ (Total Refrigerant Quantity × Benchmark Leakage Factor × Benchmark Emission Factor)
    """
    baseline_total = sum(q * baseline_leakage * baseline_emission_factor for q in total_quantities)
    benchmark_total = sum(q * benchmark_leakage * benchmark_emission_factor for q in total_quantities)
    return baseline_total - benchmark_total


def avoided_emission_hotwater(fuel_consumption: float, baseline_emission_factor: float,
                              benchmark_emission_factor: float) -> float:
    """
    Total Avoided Scope 1 Emission from Hot Water System Fuel Consumption.

    Formula:
    Total Hot Water System Fuel Consumption × (Baseline Emission Factor – Benchmark Emission Factor)
    """
    return fuel_consumption * (baseline_emission_factor - benchmark_emission_factor)


def avoided_emission_scope2(total_potential_saving: float, grid_emission_factor: float) -> float:
    """
    Total Avoided Scope 2 Emission.

    Formula:
    Total Potential Energy Savings for Electricity × Grid Emission Factor
    """
    return total_potential_saving * grid_emission_factor


def total_carbon_emission_reduction(avoided_refrigerants: float, avoided_hotwater: float,
                                    avoided_scope2: float) -> float:
    """
    Total Emission Reduction from Scope 1 and Scope 2.

    Formula:
    Total Carbon Emission Reduction = Avoided Emission from Refrigerants + Avoided Emission from Hot Water + Avoided Scope 2 Emission
    """
    return avoided_refrigerants + avoided_hotwater + avoided_scope2
