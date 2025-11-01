"""
Risk-Free Rate (RFR) Rate Tables
Ports VBA arorate() function for ARO discount rate calculations
"""

from datetime import date
from typing import Dict, List, Tuple
import csv


class RFRRateTable:
    """
    Risk-Free Rate lookup table
    Ports VBA arorate() function logic
    """
    
    def __init__(self):
        self.rate_tables: Dict[int, List[Tuple[date, float]]] = {
            1: [],  # Table 1
            2: [],  # Table 2
            3: []   # Table 3
        }
        self._initialize_default_rates()
    
    def _initialize_default_rates(self):
        """Initialize with default rate tables similar to Excel"""
        # Example rates - in production, these would be loaded from database or CSV
        default_rates = [
            # Table 1 rates
            (1, date(2019, 5, 1), 7.03),
            (1, date(2019, 3, 31), 7.41),
            (1, date(2019, 3, 1), 7.35),
            (1, date(2019, 2, 1), 7.59),
            (1, date(2019, 1, 1), 7.48),
            (1, date(2018, 12, 1), 7.37),
            (1, date(2018, 11, 1), 7.61),
            (1, date(2018, 10, 1), 7.85),
            (1, date(2018, 9, 1), 8.02),
            (1, date(2018, 8, 1), 7.95),
            (1, date(2018, 7, 1), 7.77),
            (1, date(2018, 6, 1), 7.90),
            (1, date(2018, 5, 1), 7.83),
            (1, date(2018, 4, 1), 7.77),
            (1, date(2018, 3, 1), 7.40),
            (1, date(2018, 2, 1), 7.73),
            (1, date(2018, 1, 1), 7.43),
            (1, date(2017, 12, 1), 7.32),
            (1, date(2017, 11, 1), 7.06),
            (1, date(2017, 10, 1), 6.86),
            (1, date(2017, 9, 1), 6.67),
            (1, date(2017, 8, 1), 6.53),
            (1, date(2017, 7, 1), 6.47),
            (1, date(2017, 6, 1), 6.51),
            (1, date(2017, 5, 1), 6.66),
            (1, date(2017, 4, 1), 6.96),
            (1, date(2017, 3, 1), 6.69),
            (1, date(2017, 2, 1), 6.87),
            (1, date(2017, 1, 1), 6.41),
            (1, date(2016, 12, 1), 6.52),
            (1, date(2016, 11, 1), 6.25),
            (1, date(2016, 10, 1), 6.89),
            (1, date(2016, 9, 1), 6.96),
            (1, date(2016, 8, 1), 7.11),
            (1, date(2016, 7, 1), 7.16),
            (1, date(2012, 3, 31), 7.45),
            
            # Table 2 rates
            (2, date(2019, 3, 1), 8.51),
            
            # Table 3 - empty for now
        ]
        
        for table_num, rate_date, rate_value in default_rates:
            if table_num in self.rate_tables:
                self.rate_tables[table_num].append((rate_date, rate_value / 100))  # Convert to decimal
        
        # Sort by date descending
        for table_num in self.rate_tables:
            self.rate_tables[table_num].sort(key=lambda x: x[0], reverse=True)
    
    def get_rate(self, rate_date: date, table: int) -> float:
        """
        Get risk-free rate for a given date and table
        Ports VBA: arorate(date1 As Double, table As Integer)
        
        Args:
            rate_date: Date to look up rate for
            table: Table number (1, 2, or 3)
            
        Returns:
            Risk-free rate as decimal (e.g., 0.0703 for 7.03%)
        """
        if table == 0 or table not in self.rate_tables:
            return 0.0
        
        # Find the rate for the given date
        for table_date, rate in self.rate_tables[table]:
            if table_date <= rate_date:
                return rate
        
        # If no rate found for that date, return the most recent available rate
        if self.rate_tables[table]:
            return self.rate_tables[table][0][1]
        
        return 0.0
    
    def load_from_file(self, filename: str):
        """Load RFR rates from CSV file"""
        with open(filename, 'r') as f:
            reader = csv.reader(f)
            # Skip header
            next(reader)
            for row in reader:
                if len(row) >= 3:
                    try:
                        table = int(row[0])
                        date_str = row[1]
                        rate = float(row[2]) / 100  # Convert percentage to decimal
                        
                        # Parse date (assuming format YYYY-MM-DD)
                        rate_date = date.fromisoformat(date_str)
                        
                        if table in self.rate_tables:
                            self.rate_tables[table].append((rate_date, rate))
                    except (ValueError, IndexError):
                        continue
        
        # Sort by date descending
        for table_num in self.rate_tables:
            self.rate_tables[table_num].sort(key=lambda x: x[0], reverse=True)


# Global instance
_rfr_table = RFRRateTable()


def get_aro_rate(rate_date: date, table: int) -> float:
    """
    Convenience function to get ARO rate
    Uses global RFR table instance
    """
    return _rfr_table.get_rate(rate_date, table)


def update_rfr_table(rates: Dict[int, List[Tuple[date, float]]]):
    """Update the global RFR table with new rates"""
    global _rfr_table
    _rfr_table.rate_tables = rates
    for table_num in _rfr_table.rate_tables:
        _rfr_table.rate_tables[table_num].sort(key=lambda x: x[0], reverse=True)

