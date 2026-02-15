# trade_analytics.py
"""
Trade analytics and performance tracking system.
Logs all trades and calculates performance metrics.
"""

import os
import json
import time
import numpy as np
from datetime import datetime
from config import ENABLE_TRADE_LOGGING, LOG_FILE_PATH


class TradeAnalytics:
    """Tracks and analyzes trading performance."""
    
    def __init__(self, log_file=LOG_FILE_PATH):
        self.log_file = log_file
        self.trades = []
        self.equity_curve = []
        self.daily_pnl = {}
        
        # Create log directory if it doesn't exist
        if ENABLE_TRADE_LOGGING:
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir)
    
    def log_trade(self, trade_data):
        """
        Logs a completed trade.
        
        Args:
            trade_data: Dictionary with trade details (entry, exit, pnl, etc.)
        """
        if not ENABLE_TRADE_LOGGING:
            return
        
        # Add timestamp
        trade_data['timestamp'] = datetime.now().isoformat()
        
        # Store in memory
        self.trades.append(trade_data)
        
        # Write to file
        try:
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(trade_data) + '\n')
        except Exception as e:
            print(f"[WARNING] Failed to write trade log: {e}")
    
    def log_equity_point(self, equity, timestamp=None):
        """Records equity at a point in time for equity curve."""
        if timestamp is None:
            timestamp = time.time()
        
        self.equity_curve.append({
            'timestamp': timestamp,
            'equity': equity
        })
    
    def calculate_sharpe_ratio(self, risk_free_rate=0.02):
        """
        Calculates Sharpe ratio from trade returns.
        
        Args:
            risk_free_rate: Annual risk-free rate (default 2%)
        
        Returns:
            Sharpe ratio or None if insufficient data
        """
        if len(self.trades) < 2:
            return None
        
        returns = [t['pnl_pct'] for t in self.trades if 'pnl_pct' in t]
        
        if not returns:
            return None
        
        returns_array = np.array(returns)
        
        # Calculate excess returns (assuming trades represent periods)
        avg_return = np.mean(returns_array)
        std_return = np.std(returns_array)
        
        if std_return == 0:
            return None
        
        # Annualize (assuming daily trading)
        periods_per_year = 252  # Trading days
        sharpe = (avg_return - risk_free_rate / periods_per_year) / std_return * np.sqrt(periods_per_year)
        
        return sharpe
    
    def calculate_max_drawdown(self):
        """Calculates maximum drawdown from equity curve."""
        if len(self.equity_curve) < 2:
            return 0.0
        
        equities = [point['equity'] for point in self.equity_curve]
        peak = equities[0]
        max_dd = 0.0
        
        for equity in equities:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def get_win_rate(self):
        """Calculates win rate from completed trades."""
        if not self.trades:
            return 0.0
        
        winning_trades = sum(1 for t in self.trades if t.get('pnl', 0) > 0)
        return winning_trades / len(self.trades)
    
    def get_profit_factor(self):
        """Calculates profit factor (gross profit / gross loss)."""
        if not self.trades:
            return 0.0
        
        gross_profit = sum(t['pnl'] for t in self.trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t['pnl'] for t in self.trades if t.get('pnl', 0) < 0))
        
        if gross_loss == 0:
            return float('inf') if gross_profit > 0 else 0.0
        
        return gross_profit / gross_loss
    
    def get_average_trade_duration(self):
        """Calculates average trade duration in seconds."""
        if not self.trades:
            return 0.0
        
        durations = [t['duration'] for t in self.trades if 'duration' in t]
        
        if not durations:
            return 0.0
        
        return sum(durations) / len(durations)
    
    def get_daily_summary(self, date=None):
        """
        Gets summary of trades for a specific date.
        
        Args:
            date: Date string in YYYY-MM-DD format (default: today)
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        daily_trades = [t for t in self.trades 
                       if datetime.fromisoformat(t['timestamp']).strftime('%Y-%m-%d') == date]
        
        if not daily_trades:
            return None
        
        total_pnl = sum(t.get('pnl', 0) for t in daily_trades)
        winning = sum(1 for t in daily_trades if t.get('pnl', 0) > 0)
        
        return {
            'date': date,
            'total_trades': len(daily_trades),
            'winning_trades': winning,
            'losing_trades': len(daily_trades) - winning,
            'win_rate': winning / len(daily_trades),
            'total_pnl': total_pnl,
            'avg_pnl': total_pnl / len(daily_trades)
        }
    
    def print_performance_summary(self):
        """Prints a comprehensive performance summary."""
        if not self.trades:
            print("\n[ANALYTICS] No trades recorded yet.")
            return
        
        win_rate = self.get_win_rate()
        sharpe = self.calculate_sharpe_ratio()
        max_dd = self.calculate_max_drawdown()
        profit_factor = self.get_profit_factor()
        avg_duration = self.get_average_trade_duration()
        
        total_pnl = sum(t.get('pnl', 0) for t in self.trades)
        winning_trades = [t for t in self.trades if t.get('pnl', 0) > 0]
        losing_trades = [t for t in self.trades if t.get('pnl', 0) <= 0]
        
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        print("\n" + "="*70)
        print("PERFORMANCE SUMMARY")
        print("="*70)
        print(f"Total Trades: {len(self.trades)}")
        print(f"Winning Trades: {len(winning_trades)} ({win_rate*100:.2f}%)")
        print(f"Losing Trades: {len(losing_trades)}")
        print(f"Win Rate: {win_rate*100:.2f}%")
        print(f"Profit Factor: {profit_factor:.2f}")
        print(f"Sharpe Ratio: {sharpe:.2f}" if sharpe else "Sharpe Ratio: N/A")
        print(f"Max Drawdown: {max_dd*100:.2f}%")
        print(f"Total P&L: {total_pnl:.2f}")
        print(f"Average Win: {avg_win:.2f}")
        print(f"Average Loss: {avg_loss:.2f}")
        print(f"Avg Trade Duration: {avg_duration/60:.1f} minutes")
        print("="*70 + "\n")
    
    def export_to_csv(self, filename='trade_history.csv'):
        """Exports trade history to CSV file."""
        if not self.trades:
            print("[ANALYTICS] No trades to export.")
            return
        
        import csv
        
        try:
            with open(filename, 'w', newline='') as f:
                if self.trades:
                    writer = csv.DictWriter(f, fieldnames=self.trades[0].keys())
                    writer.writeheader()
                    writer.writerows(self.trades)
            print(f"[ANALYTICS] Trade history exported to {filename}")
        except Exception as e:
            print(f"[WARNING] Failed to export trades: {e}")
