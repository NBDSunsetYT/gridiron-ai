'use client';

import type {ComponentProps} from 'react';
import PlayerPropIntelligence from './PlayerPropIntelligence';

/** The all-NFL view shares the verified player research interface and persistence. */
export default function NflMarketIntelligence(props:Omit<ComponentProps<typeof PlayerPropIntelligence>,'mode'>){
 return <PlayerPropIntelligence {...props} mode="all"/>;
}
