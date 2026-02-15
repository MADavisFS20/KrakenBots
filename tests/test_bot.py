"""
Unit tests for trading bot indicators and risk management.
Run with: python -m pytest tests/ or python tests/test_bot.py
"""

import os
import sys
import numpy as np

# Set test environment variables before importing
os.environ['API_KEY'] = 'test_key_for_testing'
os.environ['API_SECRET'] = 'test_secret_for_testing'

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from indicators import (calculate_rsi, calculate_macd, calculate_sma, calculate_atr,
                       detect_support_resistance, analyze_volume, detect_market_regime)
from risk_manager import RiskManager
from trade_analytics import TradeAnalytics


def create_mock_ohlc(num_candles=50, base_price=50000, trend='flat'):
    """Creates mock OHLC data for testing."""
    mock_ohlc = []
    
    for i in range(num_candles):
        if trend == 'up':
            price = base_price + i * 20 + np.random.randn() * 10
        elif trend == 'down':
            price = base_price - i * 20 + np.random.randn() * 10
        else:  # flat
            price = base_price + np.random.randn() * 50
        
        mock_ohlc.append([
            1000000 + i * 300,  # timestamp
            price,              # open
            price + 20,         # high
            price - 20,         # low
            price + 5,          # close
            price,              # vwap
            100 + np.random.rand() * 50,  # volume
            10                  # count
        ])
    
    return mock_ohlc


class TestIndicators:
    """Test indicator calculations."""
    
    def test_rsi_calculation(self):
        """Test RSI calculation returns valid values."""
        data = create_mock_ohlc(50)
        rsi = calculate_rsi(data, 14)
        
        assert rsi is not None, "RSI should not be None with sufficient data"
        assert 0 <= rsi <= 100, f"RSI should be between 0-100, got {rsi}"
    
    def test_rsi_insufficient_data(self):
        """Test RSI with insufficient data returns None."""
        data = create_mock_ohlc(10)
        rsi = calculate_rsi(data, 14)
        
        assert rsi is None, "RSI should return None with insufficient data"
    
    def test_macd_calculation(self):
        """Test MACD calculation returns valid values."""
        data = create_mock_ohlc(50)
        macd, signal, hist = calculate_macd(data)
        
        assert macd is not None, "MACD line should not be None"
        assert signal is not None, "Signal line should not be None"
        assert hist is not None, "Histogram should not be None"
        assert isinstance(macd, (int, float, np.number)), "MACD should be numeric"
        assert isinstance(signal, (int, float, np.number)), "Signal should be numeric"
        assert isinstance(hist, (int, float, np.number)), "Histogram should be numeric"
    
    def test_sma_calculation(self):
        """Test SMA calculation."""
        data = create_mock_ohlc(30)
        sma = calculate_sma(data, 20)
        
        assert sma is not None, "SMA should not be None"
        assert sma > 0, "SMA should be positive for positive prices"
    
    def test_atr_calculation(self):
        """Test ATR calculation."""
        data = create_mock_ohlc(30)
        atr = calculate_atr(data, 14)
        
        assert atr is not None, "ATR should not be None"
        assert atr > 0, "ATR should be positive"
    
    def test_support_resistance_detection(self):
        """Test support/resistance level detection."""
        data = create_mock_ohlc(100)
        support, resistance = detect_support_resistance(data, 50)
        
        assert isinstance(support, list), "Support should be a list"
        assert isinstance(resistance, list), "Resistance should be a list"
    
    def test_volume_analysis(self):
        """Test volume analysis."""
        data = create_mock_ohlc(30)
        vol_signal, avg_vol, current_vol = analyze_volume(data, 20)
        
        assert vol_signal in [-1, 0, 1], "Volume signal should be -1, 0, or 1"
        assert avg_vol is not None, "Average volume should not be None"
        assert current_vol is not None, "Current volume should not be None"
    
    def test_market_regime_detection(self):
        """Test market regime detection."""
        data = create_mock_ohlc(50)
        regime, adx = detect_market_regime(data, 14)
        
        assert regime in ['trending', 'ranging', None], f"Invalid regime: {regime}"
        if adx is not None:
            assert adx >= 0, "ADX should be non-negative"


class TestRiskManager:
    """Test risk management functionality."""
    
    def test_initialization(self):
        """Test RiskManager initialization."""
        rm = RiskManager(10000.0)
        
        assert rm.initial_equity == 10000.0
        assert rm.current_equity == 10000.0
        assert rm.peak_equity == 10000.0
        assert rm.max_drawdown == 0.0
        assert len(rm.active_positions) == 0
    
    def test_equity_update(self):
        """Test equity update and drawdown calculation."""
        rm = RiskManager(10000.0)
        
        # Update to higher equity
        dd = rm.update_equity(11000.0)
        assert rm.current_equity == 11000.0
        assert rm.peak_equity == 11000.0
        assert dd == 0.0
        
        # Update to lower equity (drawdown)
        dd = rm.update_equity(10500.0)
        assert rm.current_equity == 10500.0
        assert dd > 0, "Drawdown should be positive"
    
    def test_circuit_breaker(self):
        """Test circuit breaker activation."""
        rm = RiskManager(10000.0)
        rm.update_equity(10000.0)
        
        # Drop equity by >5% to trigger circuit breaker
        rm.update_equity(9400.0)
        
        assert rm.circuit_breaker_active, "Circuit breaker should activate"
        
        can_trade, reason = rm.can_open_position()
        assert not can_trade, "Should not be able to trade with circuit breaker"
    
    def test_position_sizing(self):
        """Test position size calculation."""
        rm = RiskManager(10000.0)
        
        position_size, stop_loss = rm.calculate_position_size(50000, 100, 1.0)
        
        assert position_size > 0, "Position size should be positive"
        assert stop_loss > 0, "Stop loss should be positive"
        assert stop_loss < 50000, "Stop loss should be below entry price"
    
    def test_add_remove_position(self):
        """Test adding and removing positions."""
        rm = RiskManager(10000.0)
        
        # Add position
        pos = rm.add_position(50000, 0.1, 49800)
        assert len(rm.active_positions) == 1
        assert pos['entry_price'] == 50000
        assert pos['volume'] == 0.1
        
        # Remove position
        trade_record = rm.remove_position(0, 51000, 'profit_target')
        assert len(rm.active_positions) == 0
        assert trade_record['pnl'] > 0, "Should have positive P&L"
    
    def test_position_updates(self):
        """Test position update logic."""
        rm = RiskManager(10000.0)
        rm.add_position(50000, 0.1, 49800)
        
        # Test hold action
        action, volume, reason = rm.update_position(0, 50100)
        assert action in ['hold', 'partial_exit', 'full_exit', 'update_stop']
    
    def test_statistics(self):
        """Test statistics calculation."""
        rm = RiskManager(10000.0)
        
        # Add and close some trades
        rm.add_position(50000, 0.1, 49800)
        rm.remove_position(0, 51000, 'profit')
        
        rm.add_position(51000, 0.1, 50800)
        rm.remove_position(0, 50500, 'stop_loss')
        
        stats = rm.get_statistics()
        
        assert stats['total_trades'] == 2
        assert stats['winning_trades'] == 1
        assert stats['losing_trades'] == 1
        assert 0 <= stats['win_rate'] <= 1


class TestTradeAnalytics:
    """Test trade analytics functionality."""
    
    def test_initialization(self):
        """Test TradeAnalytics initialization."""
        ta = TradeAnalytics()
        
        assert len(ta.trades) == 0
        assert len(ta.equity_curve) == 0
    
    def test_trade_logging(self):
        """Test trade logging."""
        ta = TradeAnalytics()
        
        trade = {
            'entry_price': 50000,
            'exit_price': 51000,
            'volume': 0.1,
            'pnl': 100,
            'pnl_pct': 0.02,
            'entry_time': 1000000,
            'exit_time': 1000300,
            'duration': 300,
            'exit_reason': 'target_1'
        }
        
        ta.log_trade(trade)
        assert len(ta.trades) == 1
    
    def test_equity_curve(self):
        """Test equity curve tracking."""
        ta = TradeAnalytics()
        
        ta.log_equity_point(10000, 1000000)
        ta.log_equity_point(10500, 1000300)
        
        assert len(ta.equity_curve) == 2
    
    def test_win_rate(self):
        """Test win rate calculation."""
        ta = TradeAnalytics()
        
        # Log winning trade
        ta.log_trade({
            'pnl': 100,
            'pnl_pct': 0.02,
            'entry_time': 1000000,
            'exit_time': 1000300,
            'duration': 300,
        })
        
        # Log losing trade
        ta.log_trade({
            'pnl': -50,
            'pnl_pct': -0.01,
            'entry_time': 1000300,
            'exit_time': 1000600,
            'duration': 300,
        })
        
        win_rate = ta.get_win_rate()
        assert win_rate == 0.5, f"Win rate should be 50%, got {win_rate}"
    
    def test_profit_factor(self):
        """Test profit factor calculation."""
        ta = TradeAnalytics()
        
        ta.log_trade({'pnl': 200})
        ta.log_trade({'pnl': -100})
        
        pf = ta.get_profit_factor()
        assert pf == 2.0, f"Profit factor should be 2.0, got {pf}"
    
    def test_sharpe_ratio(self):
        """Test Sharpe ratio calculation."""
        ta = TradeAnalytics()
        
        # Need multiple trades for Sharpe ratio
        for i in range(10):
            ta.log_trade({
                'pnl': 10 + i * 2,
                'pnl_pct': 0.01 + i * 0.001
            })
        
        sharpe = ta.calculate_sharpe_ratio()
        assert sharpe is not None, "Sharpe ratio should not be None"
    
    def test_max_drawdown(self):
        """Test maximum drawdown calculation."""
        ta = TradeAnalytics()
        
        # Create equity curve with drawdown
        ta.log_equity_point(10000, 1000000)
        ta.log_equity_point(11000, 1000300)
        ta.log_equity_point(10500, 1000600)
        ta.log_equity_point(12000, 1000900)
        
        max_dd = ta.calculate_max_drawdown()
        assert max_dd > 0, "Should have some drawdown"
        assert max_dd < 1, "Drawdown should be less than 100%"


if __name__ == '__main__':
    print("Running unit tests...\n")
    
    # Run tests manually
    test_indicators = TestIndicators()
    test_risk = TestRiskManager()
    test_analytics = TestTradeAnalytics()
    
    print("Testing Indicators...")
    test_indicators.test_rsi_calculation()
    test_indicators.test_rsi_insufficient_data()
    test_indicators.test_macd_calculation()
    test_indicators.test_sma_calculation()
    test_indicators.test_atr_calculation()
    test_indicators.test_support_resistance_detection()
    test_indicators.test_volume_analysis()
    test_indicators.test_market_regime_detection()
    print("✓ All indicator tests passed\n")
    
    print("Testing Risk Manager...")
    test_risk.test_initialization()
    test_risk.test_equity_update()
    test_risk.test_circuit_breaker()
    test_risk.test_position_sizing()
    test_risk.test_add_remove_position()
    test_risk.test_position_updates()
    test_risk.test_statistics()
    print("✓ All risk manager tests passed\n")
    
    print("Testing Trade Analytics...")
    test_analytics.test_initialization()
    test_analytics.test_trade_logging()
    test_analytics.test_equity_curve()
    test_analytics.test_win_rate()
    test_analytics.test_profit_factor()
    test_analytics.test_sharpe_ratio()
    test_analytics.test_max_drawdown()
    print("✓ All analytics tests passed\n")
    
    print("✅ ALL TESTS PASSED!")
