/* Stage111Z31K: independent x87 periodic Hann RMS reference, no device IO.

   Source-derived from user-private Delphi function structure 008C1064:
      x87 extended angle = i * (2*pi)_Extended / 262144_Single;
      Cos(angle), 1 - cos, Sqrt(1.5)_Extended, final FSTP Single.
   The 80-bit 2*pi constant is a mathematical constant, not source code.
   This file is an independently written minimal x87 replay, not a copy
   of private Pascal/disassembly, and contains NO original measurement.

   On x86 GCC or clang:
      cc -O2 -fno-fast-math -std=gnu11 hann_x87_reference.c -o hann_x87_ref
      ./hann_x87_ref | sha256sum

   Expected source-derived candidate for 262144 Float32 entries:
      df10f6ab747656aefaeb17dee2764dd552e80cb738a5390108b8943615398069

   Agreement with four measured original Single words and NumPy+four fixes
   does NOT certify entire original in-process table or x87 FFT twiddles.
*/
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#if !defined(__i386__) && !defined(__x86_64__)
#error "The independent reference requires an x87-capable x86 target"
#endif

/* Binary 80-bit extended constants for mathematically standard 2*pi,
   and 1.5 (not embedded original firmware or measurement material). */
static const unsigned char two_pi_ext[10] = {
    0x35,0xC2,0x68,0x21,0xA2,0xDA,0x0F,0xC9,0x01,0x40
};
static const unsigned char one_point_five_ext[10] = {
    0,0,0,0,0,0,0,0xC0,0xFF,0x3F
};

static float single_hann(unsigned index, unsigned short control)
{
    unsigned short prev;
    long double two_pi = 0, one5 = 0, angle, numerator, den;
    float fft_table_period = 262144.0f, result;
    int i = (int)index;
    memcpy(&two_pi,two_pi_ext,sizeof(two_pi_ext));
    memcpy(&one5,one_point_five_ext,sizeof(one_point_five_ext));
    __asm__ volatile("fnstcw %0":"=m"(prev));
    __asm__ volatile("fldcw %0"::"m"(control));
    __asm__ volatile(
        "fildl %1; fldt %2; fmulp %%st,%%st(1); "
        "fdivs %3; fstpt %0"
        :"=m"(angle):"m"(i),"m"(two_pi),"m"(fft_table_period):"st");
    __asm__ volatile(
        "fldt %1; fcos; fld1; fsubp %%st,%%st(1); fstpt %0"
        :"=m"(numerator):"m"(angle):"st");
    __asm__ volatile("fldt %1; fsqrt; fstpt %0"
        :"=m"(den):"m"(one5):"st");
    __asm__ volatile(
        "fldt %1; fldt %2; fdivrp %%st,%%st(1); fstps %0"
        :"=m"(result):"m"(numerator),"m"(den):"st");
    __asm__ volatile("fldcw %0"::"m"(prev));
    return result;
}

int main(void)
{
    /* The x87 control word is an explicitly selected research candidate
       based on the operator's Win32 debugger notes. */
    const unsigned short control_word = 0x1372;
    for (unsigned i=0;i<262144;i++) {
        float value=single_hann(i,control_word);
        if(fwrite(&value,sizeof(value),1,stdout)!=1)
            return 1;
    }
    return 0;
}
