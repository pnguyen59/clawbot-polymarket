#!/usr/bin/env python3
"""
Tests for configuration schema and CLI argument parsing.
"""

import pytest
import json
import tempfile
import os
from mock_trader import (
    CONFIG_SCHEMA,
    get_default_config,
    validate_config_value,
    validate_config,
    load_config_from_file,
    save_config_to_file,
    create_argument_parser,
    parse_args_to_config,
)


class TestConfigSchema:
    """Tests for configuration schema."""
    
    def test_schema_has_all_required_keys(self):
        """Verify schema contains all expected configuration keys."""
        required_keys = [
            'rsi_enabled',
            'rsi_period',
            'rsi_signal_memory_size',
            'rsi_require_confirmation',
            'min_momentum_pct',
            'min_profit_per_share',
            'target_profit_per_trade',
            'max_position_size',
            'target_sell_spread',
            'mock_trading',
            'mock_balance',
        ]
        
        for key in required_keys:
            assert key in CONFIG_SCHEMA, f"Missing key: {key}"
    
    def test_schema_has_type_for_all_keys(self):
        """Verify all schema entries have a type defined."""
        for key, schema in CONFIG_SCHEMA.items():
            assert 'type' in schema, f"Missing type for key: {key}"
    
    def test_schema_has_default_for_all_keys(self):
        """Verify all schema entries have a default value."""
        for key, schema in CONFIG_SCHEMA.items():
            assert 'default' in schema, f"Missing default for key: {key}"


class TestGetDefaultConfig:
    """Tests for get_default_config function."""
    
    def test_returns_dict(self):
        """Verify get_default_config returns a dictionary."""
        config = get_default_config()
        assert isinstance(config, dict)
    
    def test_has_all_schema_keys(self):
        """Verify default config has all schema keys."""
        config = get_default_config()
        for key in CONFIG_SCHEMA:
            assert key in config, f"Missing key in default config: {key}"
    
    def test_default_values_match_schema(self):
        """Verify default values match schema defaults."""
        config = get_default_config()
        for key, schema in CONFIG_SCHEMA.items():
            assert config[key] == schema['default'], f"Default mismatch for {key}"
    
    def test_mock_trading_default_true(self):
        """Verify mock_trading defaults to True."""
        config = get_default_config()
        assert config['mock_trading'] is True
    
    def test_rsi_enabled_default_false(self):
        """Verify rsi_enabled defaults to False."""
        config = get_default_config()
        assert config['rsi_enabled'] is False
    
    def test_target_profit_default_15(self):
        """Verify target_profit_per_trade defaults to 15.0."""
        config = get_default_config()
        assert config['target_profit_per_trade'] == 15.0
    
    def test_mock_balance_default_1000(self):
        """Verify mock_balance defaults to 1000.0."""
        config = get_default_config()
        assert config['mock_balance'] == 1000.0


class TestValidateConfigValue:
    """Tests for validate_config_value function."""
    
    def test_valid_bool_value(self):
        """Test validation of valid boolean value."""
        is_valid, error = validate_config_value('mock_trading', True)
        assert is_valid is True
        assert error is None
    
    def test_valid_int_value(self):
        """Test validation of valid integer value."""
        is_valid, error = validate_config_value('rsi_period', 7)
        assert is_valid is True
        assert error is None
    
    def test_valid_float_value(self):
        """Test validation of valid float value."""
        is_valid, error = validate_config_value('target_profit_per_trade', 20.0)
        assert is_valid is True
        assert error is None
    
    def test_invalid_type(self):
        """Test validation rejects wrong type."""
        is_valid, error = validate_config_value('mock_trading', "true")
        assert is_valid is False
        assert "must be bool" in error
    
    def test_value_below_min(self):
        """Test validation rejects value below minimum."""
        is_valid, error = validate_config_value('rsi_period', 1)
        assert is_valid is False
        assert "must be >=" in error
    
    def test_value_above_max(self):
        """Test validation rejects value above maximum."""
        is_valid, error = validate_config_value('rsi_period', 100)
        assert is_valid is False
        assert "must be <=" in error
    
    def test_unknown_key(self):
        """Test validation rejects unknown key."""
        is_valid, error = validate_config_value('unknown_key', 123)
        assert is_valid is False
        assert "Unknown configuration key" in error
    
    def test_nullable_field_accepts_none(self):
        """Test nullable field accepts None value."""
        is_valid, error = validate_config_value('max_position_size', None)
        assert is_valid is True
        assert error is None
    
    def test_int_accepted_for_float_field(self):
        """Test integer is accepted for float field."""
        is_valid, error = validate_config_value('target_profit_per_trade', 20)
        assert is_valid is True
        assert error is None


class TestValidateConfig:
    """Tests for validate_config function."""
    
    def test_valid_config(self):
        """Test validation of valid configuration."""
        config = get_default_config()
        is_valid, errors = validate_config(config)
        assert is_valid is True
        assert len(errors) == 0
    
    def test_invalid_config_returns_errors(self):
        """Test validation returns errors for invalid config."""
        config = get_default_config()
        config['rsi_period'] = 1  # Below minimum
        is_valid, errors = validate_config(config)
        assert is_valid is False
        assert len(errors) > 0


class TestConfigFile:
    """Tests for config file loading and saving."""
    
    def test_save_and_load_config(self):
        """Test saving and loading configuration from file."""
        config = get_default_config()
        config['target_profit_per_trade'] = 25.0
        config['mock_balance'] = 5000.0
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            filepath = f.name
        
        try:
            save_config_to_file(config, filepath)
            loaded_config = load_config_from_file(filepath)
            
            assert loaded_config['target_profit_per_trade'] == 25.0
            assert loaded_config['mock_balance'] == 5000.0
        finally:
            os.unlink(filepath)
    
    def test_load_config_with_unknown_keys_warns(self, capsys):
        """Test loading config with unknown keys prints warning."""
        config_data = {
            'mock_trading': True,
            'unknown_key': 'value'
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            filepath = f.name
        
        try:
            loaded_config = load_config_from_file(filepath)
            captured = capsys.readouterr()
            assert "unknown_key" in captured.out
            assert "ignoring" in captured.out.lower()
        finally:
            os.unlink(filepath)


class TestArgumentParser:
    """Tests for CLI argument parsing."""
    
    def test_parser_creation(self):
        """Test argument parser is created successfully."""
        parser = create_argument_parser()
        assert parser is not None
    
    def test_default_args(self):
        """Test parsing with no arguments returns defaults."""
        config = parse_args_to_config([])
        assert config['mock_trading'] is True
        assert config['rsi_enabled'] is False
        assert config['target_profit_per_trade'] == 15.0
        assert config['mock_balance'] == 1000.0
    
    def test_mock_flag(self):
        """Test --mock flag sets mock_trading to True."""
        config = parse_args_to_config(['--mock'])
        assert config['mock_trading'] is True
    
    def test_no_mock_flag(self):
        """Test --no-mock flag sets mock_trading to False."""
        config = parse_args_to_config(['--no-mock'])
        assert config['mock_trading'] is False
    
    def test_rsi_enabled_flag(self):
        """Test --rsi-enabled flag sets rsi_enabled to True."""
        config = parse_args_to_config(['--rsi-enabled'])
        assert config['rsi_enabled'] is True
    
    def test_no_rsi_flag(self):
        """Test --no-rsi flag sets rsi_enabled to False."""
        config = parse_args_to_config(['--no-rsi'])
        assert config['rsi_enabled'] is False
    
    def test_target_profit_flag(self):
        """Test --target-profit flag sets target_profit_per_trade."""
        config = parse_args_to_config(['--target-profit', '25.0'])
        assert config['target_profit_per_trade'] == 25.0
    
    def test_mock_balance_flag(self):
        """Test --mock-balance flag sets mock_balance."""
        config = parse_args_to_config(['--mock-balance', '5000.0'])
        assert config['mock_balance'] == 5000.0
    
    def test_rsi_period_flag(self):
        """Test --rsi-period flag sets rsi_period."""
        config = parse_args_to_config(['--rsi-period', '14'])
        assert config['rsi_period'] == 14
    
    def test_multiple_flags(self):
        """Test multiple flags together."""
        config = parse_args_to_config([
            '--rsi-enabled',
            '--target-profit', '30.0',
            '--mock-balance', '2000.0'
        ])
        assert config['rsi_enabled'] is True
        assert config['target_profit_per_trade'] == 30.0
        assert config['mock_balance'] == 2000.0
    
    def test_config_file_flag(self):
        """Test --config flag loads from file."""
        config_data = {
            'target_profit_per_trade': 50.0,
            'mock_balance': 10000.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            filepath = f.name
        
        try:
            config = parse_args_to_config(['--config', filepath])
            assert config['target_profit_per_trade'] == 50.0
            assert config['mock_balance'] == 10000.0
        finally:
            os.unlink(filepath)
    
    def test_cli_overrides_config_file(self):
        """Test CLI arguments override config file values."""
        config_data = {
            'target_profit_per_trade': 50.0,
            'mock_balance': 10000.0
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(config_data, f)
            filepath = f.name
        
        try:
            config = parse_args_to_config([
                '--config', filepath,
                '--target-profit', '75.0'
            ])
            # CLI should override file
            assert config['target_profit_per_trade'] == 75.0
            # File value should be preserved
            assert config['mock_balance'] == 10000.0
        finally:
            os.unlink(filepath)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
