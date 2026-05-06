import { describe, expect, test } from 'vitest'
import { mount } from '@vue/test-utils'

import StatusPill from './StatusPill.vue'

describe('StatusPill', () => {
  test('renders label', () => {
    const wrapper = mount(StatusPill, {
      props: { status: 'success', label: 'healthy' },
    })

    expect(wrapper.text()).toContain('healthy')
    expect(wrapper.classes()).toContain('status-pill')
  })
})
