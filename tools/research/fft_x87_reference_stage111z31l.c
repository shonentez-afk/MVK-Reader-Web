/* Stage111Z31L: independent x87 radix-2 + Hann FFT power reference.
 * This research oracle reconstructs instruction-level *arithmetic*
 * without original Delphi source, buffers, firmware or device data.
 * It reads one pre-FFT prepared Float32 frame from stdin and emits
 * N/2 little-endian Float32 powers to stdout.
 *
 * cc -O2 -std=gnu11 -ffp-contract=off -fno-fast-math \
 *    fft_x87_reference_stage111z31l.c -lm -o x87fft
 * x87fft 4096 < synthetic_f32.bin > synthetic_power_f32.bin
 *
 * Requirements: x86/x86_64 with x87, little-endian IEEE-754 Float32.
 * The original Win32 process has NOT been bitwise authenticated by
 * this oracle. No DC subtraction or integration is performed here.
 */
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <errno.h>
#if !defined(__x86_64__) && !defined(__i386__)
#error "x87 instruction support required"
#endif
#define MAX_N 262144U

/* Math constants, not any proprietary original data or calibration. */
static const unsigned char pi2[10]={
    0x35,0xC2,0x68,0x21,0xA2,0xDA,0x0F,0xC9,0x01,0x40};
static const unsigned char one5[10]={
    0,0,0,0,0,0,0,0xC0,0xFF,0x3F};

static long double const80(const unsigned char *bytes) {
    long double v=0;
    memcpy(&v,bytes,10);
    return v;
}
static inline float single(long double v) {
    volatile float out=(float)v;
    return out;
}
static long double sin_x87(long double x) {
    long double y;
    __asm__ volatile("fldt %1; fsin; fstpt %0":"=m"(y):"m"(x):"st");
    return y;
}
static long double cos_x87(long double x) {
    long double y;
    __asm__ volatile("fldt %1; fcos; fstpt %0":"=m"(y):"m"(x):"st");
    return y;
}
static float hann(unsigned j) {
    long double angle=((long double)j*const80(pi2))/262144.0L;
    return single((1.0L-cos_x87(angle))/sqrtl(const80(one5)));
}
static int valid_n(unsigned n) {
    return n>=1024 && n<=MAX_N && (n&(n-1))==0;
}
static unsigned reverse_bits(unsigned v,unsigned bits) {
    unsigned out=0;
    while(bits--) { out=(out<<1)|(v&1U); v>>=1; }
    return out;
}
int main(int argc,char **argv) {
    if(argc!=2) return 2;
    char *end=NULL; errno=0;
    unsigned long requested=strtoul(argv[1],&end,10);
    if(errno || !end || *end || requested>MAX_N ||
       !valid_n((unsigned)requested)) return 2;
    const unsigned n=(unsigned)requested;
    float *in=calloc(n,sizeof(float)),*re=calloc(n,sizeof(float)),
          *im=calloc(n,sizeof(float));
    if(!in || !re || !im) return 4;
    if(fread(in,sizeof(float),n,stdin)!=n) return 3;
    unsigned bits=0;
    for(unsigned v=n;v>1;v>>=1) bits++;
    unsigned short prior,cw=0x1372;
    __asm__ volatile("fnstcw %0":"=m"(prior));
    __asm__ volatile("fldcw %0"::"m"(cw));
    for(unsigned i=0;i<n;i++) {
        if(!isfinite(in[i])) return 5;
        re[reverse_bits(i,bits)]=single(
            (long double)in[i]*hann(i*(MAX_N/n)));
    }
    /* Reconstruct source 007CC198 butterfly ordering, Single stores. */
    const float pi2_single=0x1.921fb6p+2f;
    for(unsigned m=2;m<=n;m*=2) {
        unsigned half=m/2;
        float angle=single((long double)pi2_single/(long double)m);
        float sinhalf=single(sin_x87((long double)angle*0.5L));
        float alpha=single(2.0L*(long double)sinhalf*sinhalf);
        float beta=single(sin_x87((long double)angle));
        float wr=1.0f,wi=0.0f;
        for(unsigned k=0;k<half;k++) {
            for(unsigned j=k;j<n;j+=m) {
                const unsigned right=j+half;
                const float tr=single(
                    (long double)wr*re[right]-(long double)wi*im[right]);
                const float ti=single(
                    (long double)wr*im[right]+(long double)wi*re[right]);
                const float lr=re[j],li=im[j];
                re[right]=single((long double)lr-tr);
                im[right]=single((long double)li-ti);
                re[j]=single((long double)lr+tr);
                im[j]=single((long double)li+ti);
            }
            float temp=single((long double)alpha*wr+(long double)beta*wi);
            float next_wi=single(
                (long double)wi-((long double)alpha*wi-(long double)beta*wr));
            float next_wr=single((long double)wr-temp);
            wr=next_wr;wi=next_wi;
        }
    }
    __asm__ volatile("fldcw %0"::"m"(prior));
    for(unsigned k=0;k<n/2;k++) {
        const float power=single(
            (long double)re[k]*re[k]+(long double)im[k]*im[k]);
        if(fwrite(&power,sizeof(power),1,stdout)!=1) return 7;
    }
    free(in); free(re); free(im);
    return 0;
}
