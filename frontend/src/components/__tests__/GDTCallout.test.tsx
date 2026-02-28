import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GDTCallout } from '../GDTCallout';
import type { GDTCallout as GDTCalloutType } from '../../types';

const positionCallout: GDTCalloutType = {
  feature: '4x M6 bolt holes',
  symbol: '\u2295',
  symbol_name: 'position',
  tolerance_value: '\u22050.25',
  unit: 'mm',
  modifier: 'MMC',
  modifier_symbol: '\u24C2',
  datum_references: ['A', 'B'],
  feature_control_frame: '|\u2295| \u22050.25 \u24C2 | A | B |',
  reasoning: 'Position control for bolt pattern',
};

const flatnessCallout: GDTCalloutType = {
  feature: 'mounting face',
  symbol: '\u25B1',
  symbol_name: 'flatness',
  tolerance_value: '0.1',
  unit: 'mm',
  datum_references: [],
  feature_control_frame: '|\u25B1| 0.1 |',
  reasoning: 'Flatness on primary datum surface',
};

describe('GDTCallout', () => {
  it('renders the geometric symbol', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByTitle('position')).toHaveTextContent('\u2295');
  });

  it('renders tolerance value with modifier', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByText(/\u22050\.25/)).toBeInTheDocument();
    expect(screen.getByText(/\u24C2/)).toBeInTheDocument();
  });

  it('renders datum references', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
  });

  it('renders feature label below the frame', () => {
    render(<GDTCallout callout={positionCallout} />);
    expect(screen.getByText(/Position/i)).toBeInTheDocument();
    expect(screen.getByText(/4x M6 bolt holes/)).toBeInTheDocument();
  });

  it('renders form control without datum cells', () => {
    render(<GDTCallout callout={flatnessCallout} />);
    expect(screen.getByTitle('flatness')).toHaveTextContent('\u25B1');
    expect(screen.queryByText('A')).not.toBeInTheDocument();
  });
});
