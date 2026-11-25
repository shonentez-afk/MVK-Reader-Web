package main

// The form's physical storage/configuration outlives one connection.
// This independent fence limits each display window to one contiguous,
// actually received input epoch; it never resets counters or certifies an
// aggregate RAW or BIN. A start is a local byte cursor for TACH and an
// element cursor for ADC, matching the selected channel's FRxPos domain.
type sourceDisplayEpoch struct {
	SocketAttempt        uint64 `json:"socket_attempt"`
	ContinuityGeneration uint64 `json:"continuity_generation"`
	StartPos             uint64 `json:"start_pos_64"`
}

func (c *sourceOriginalChannelRing) cutDisplayHistory() {
	// Repeated boundaries without a single intervening stored sample have
	// no displayed data to supersede. A reconnect also changes socket ID.
	if c.displayGeneration == 0 || c.displayStart != c.rxPos {
		c.displayGeneration++
		c.displayStart = c.rxPos
	}
}

func (r *sourceOriginalStorageRing) cutAllDisplayHistory() {
	for i := range r.channels {
		r.channels[i].cutDisplayHistory()
	}
}

func (r *sourceOriginalStorageRing) beginDisplaySocket(attempt uint64) {
	if r.displaySocketAttempt != attempt {
		r.displaySocketAttempt = attempt
		r.cutAllDisplayHistory()
	}
}

func (r *sourceOriginalStorageRing) displayEpoch(channel int) *sourceDisplayEpoch {
	c := &r.channels[channel]
	if r.displaySocketAttempt == 0 || c.displayGeneration == 0 ||
		c.rxPos <= c.displayStart ||
		r.displaySocketAttempt > 1 && r.rangeLatchAttempt != r.displaySocketAttempt {
		return nil
	}
	if channel < 8 && !sourceIsLiveADC(c.domain) ||
		channel >= 8 && c.domain != sourceStorageTachBytes {
		return nil
	}
	return &sourceDisplayEpoch{
		SocketAttempt:        r.displaySocketAttempt,
		ContinuityGeneration: c.displayGeneration,
		StartPos:             c.displayStart,
	}
}
