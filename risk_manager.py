# risk_manager.py
"""
Advanced risk management system with dynamic position sizing,
drawdown monitoring, and profit-taking strategies.
"""

import time
from datetime import datetime
from config import (MAX_RISK_PERCENT, ATR_STOP_MULTIPLIER, MAX_DRAWDOWN_PERCENT,
                    MAX_CONCURRENT_TRADES, TRAILING_STOP_ACTIVATION, TRAILING_STOP_DISTANCE,
                    PROFIT_TARGET_1, PROFIT_TARGET_1_SIZE, PROFIT_TARGET_2, PROFIT_TARGET_2_SIZE,
                    PROFIT_TARGET_3, PROFIT_TARGET_3_SIZE, BREAKEVEN_STOP_TRIGGER)


class RiskManager:
    """Manages risk parameters and position sizing for the trading bot."""
    
    def __init__(self, initial_equity):
        self.initial_equity = initial_equity
        self.peak_equity = initial_equity
        self.current_equity = initial_equity
        self.max_drawdown = 0.0
        self.active_positions = []
        self.trade_history = []
        self.circuit_breaker_active = False
        
    def update_equity(self, new_equity):
        """Updates current equity and tracks peak for drawdown calculation."""
        self.current_equity = new_equity
        
        # Update peak
        if new_equity > self.peak_equity:
            self.peak_equity = new_equity
        
        # Calculate current drawdown
        current_drawdown = (self.peak_equity - new_equity) / self.peak_equity
        
        # Update max drawdown
        if current_drawdown > self.max_drawdown:
            self.max_drawdown = current_drawdown
        
        # Check circuit breaker
        if current_drawdown >= MAX_DRAWDOWN_PERCENT:
            if not self.circuit_breaker_active:
                print(f"\n[CIRCUIT BREAKER] Maximum drawdown {current_drawdown*100:.2f}% reached! Trading halted.")
                self.circuit_breaker_active = True
        
        return current_drawdown
    
    def can_open_position(self):
        """Checks if we can open a new position based on risk limits."""
        if self.circuit_breaker_active:
            return False, "Circuit breaker active due to max drawdown"
        
        if len(self.active_positions) >= MAX_CONCURRENT_TRADES:
            return False, f"Maximum concurrent trades ({MAX_CONCURRENT_TRADES}) reached"
        
        return True, "OK"
    
    def calculate_position_size(self, current_price, atr_value, volatility_factor=1.0):
        """
        Calculates position size based on volatility (ATR) and risk parameters.
        
        Args:
            current_price: Current market price
            atr_value: Current ATR value
            volatility_factor: Multiplier for position size based on market conditions
        
        Returns:
            (position_size, stop_loss_price)
        """
        if atr_value <= 0 or current_price <= 0:
            return 0.0, 0.0
        
        # Risk amount in quote currency
        risk_amount = self.current_equity * MAX_RISK_PERCENT
        
        # Stop loss distance based on ATR
        stop_loss_distance = atr_value * ATR_STOP_MULTIPLIER
        
        # Calculate base position size
        # Position size = Risk Amount / Stop Loss Distance
        base_position_size = risk_amount / stop_loss_distance
        
        # Adjust for volatility - reduce size in high volatility
        adjusted_position_size = base_position_size * volatility_factor
        
        # Maximum affordable position (don't exceed available equity)
        max_affordable = self.current_equity / current_price
        
        # Final position size
        final_position_size = min(adjusted_position_size, max_affordable * 0.95)  # Keep 5% buffer
        
        # Stop loss price
        stop_loss_price = current_price - stop_loss_distance
        
        return final_position_size, stop_loss_price
    
    def add_position(self, entry_price, volume, stop_loss):
        """Adds a new position to tracking."""
        position = {
            'entry_price': entry_price,
            'volume': volume,
            'initial_volume': volume,
            'stop_loss': stop_loss,
            'highest_price': entry_price,
            'trailing_stop_active': False,
            'profit_targets_hit': [],
            'entry_time': time.time(),
            'breakeven_stop_set': False
        }
        self.active_positions.append(position)
        return position
    
    def update_position(self, position_idx, current_price):
        """
        Updates position with current price and manages stops/profit targets.
        Returns: action to take ('hold', 'partial_exit', 'full_exit', 'update_stop')
        """
        if position_idx >= len(self.active_positions):
            return 'hold', 0, None
        
        position = self.active_positions[position_idx]
        entry_price = position['entry_price']
        profit_pct = (current_price - entry_price) / entry_price
        
        # Update highest price for trailing stop
        if current_price > position['highest_price']:
            position['highest_price'] = current_price
        
        # 1. Check stop loss
        if current_price <= position['stop_loss']:
            return 'full_exit', position['volume'], 'stop_loss'
        
        # 2. Move to breakeven after initial profit
        if not position['breakeven_stop_set'] and profit_pct >= BREAKEVEN_STOP_TRIGGER:
            position['stop_loss'] = entry_price
            position['breakeven_stop_set'] = True
            return 'update_stop', 0, 'breakeven'
        
        # 3. Check profit targets
        if profit_pct >= PROFIT_TARGET_3 and '3' not in position['profit_targets_hit']:
            exit_volume = position['volume'] * PROFIT_TARGET_3_SIZE
            position['volume'] -= exit_volume
            position['profit_targets_hit'].append('3')
            return 'partial_exit', exit_volume, 'target_3'
        
        elif profit_pct >= PROFIT_TARGET_2 and '2' not in position['profit_targets_hit']:
            exit_volume = position['volume'] * PROFIT_TARGET_2_SIZE
            position['volume'] -= exit_volume
            position['profit_targets_hit'].append('2')
            return 'partial_exit', exit_volume, 'target_2'
        
        elif profit_pct >= PROFIT_TARGET_1 and '1' not in position['profit_targets_hit']:
            exit_volume = position['volume'] * PROFIT_TARGET_1_SIZE
            position['volume'] -= exit_volume
            position['profit_targets_hit'].append('1')
            
            # Activate trailing stop after first profit target
            position['trailing_stop_active'] = True
            return 'partial_exit', exit_volume, 'target_1'
        
        # 4. Update trailing stop
        if position['trailing_stop_active']:
            trailing_stop_price = position['highest_price'] * (1 - TRAILING_STOP_DISTANCE)
            if trailing_stop_price > position['stop_loss']:
                position['stop_loss'] = trailing_stop_price
                return 'update_stop', 0, 'trailing'
        
        return 'hold', 0, None
    
    def remove_position(self, position_idx, exit_price, reason):
        """Removes a position and logs it to history."""
        if position_idx >= len(self.active_positions):
            return
        
        position = self.active_positions.pop(position_idx)
        
        # Calculate final P&L
        pnl = (exit_price - position['entry_price']) * position['initial_volume']
        pnl_pct = (exit_price - position['entry_price']) / position['entry_price']
        
        # Add to history
        trade_record = {
            'entry_price': position['entry_price'],
            'exit_price': exit_price,
            'volume': position['initial_volume'],
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'entry_time': position['entry_time'],
            'exit_time': time.time(),
            'duration': time.time() - position['entry_time'],
            'exit_reason': reason,
            'profit_targets_hit': position['profit_targets_hit']
        }
        self.trade_history.append(trade_record)
        
        return trade_record
    
    def get_statistics(self):
        """Calculates trading statistics."""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'avg_pnl': 0.0,
                'max_drawdown': self.max_drawdown,
                'total_pnl': 0.0
            }
        
        winning_trades = [t for t in self.trade_history if t['pnl'] > 0]
        losing_trades = [t for t in self.trade_history if t['pnl'] <= 0]
        
        win_rate = len(winning_trades) / len(self.trade_history) if self.trade_history else 0
        total_pnl = sum(t['pnl'] for t in self.trade_history)
        avg_pnl = total_pnl / len(self.trade_history)
        
        avg_win = sum(t['pnl'] for t in winning_trades) / len(winning_trades) if winning_trades else 0
        avg_loss = sum(t['pnl'] for t in losing_trades) / len(losing_trades) if losing_trades else 0
        
        return {
            'total_trades': len(self.trade_history),
            'winning_trades': len(winning_trades),
            'losing_trades': len(losing_trades),
            'win_rate': win_rate,
            'avg_pnl': avg_pnl,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_pnl': total_pnl,
            'max_drawdown': self.max_drawdown,
            'current_equity': self.current_equity,
            'roi': (self.current_equity - self.initial_equity) / self.initial_equity
        }
    
    def reset_circuit_breaker(self):
        """Manually resets the circuit breaker (use with caution)."""
        self.circuit_breaker_active = False
        self.peak_equity = self.current_equity  # Reset peak to current
        print("[RISK MANAGER] Circuit breaker reset. Trading can resume.")
