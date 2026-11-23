/* Source-derived x87 four-mode stage (SYNTHETIC QA ONLY).
 * Input: complete N/2 Float32 Power from an independent FFT replay.
 * 007D1586..15BC: zero low bins, Max(2, Round(N/Fs/2)).
 * 007D2164: integrate once (velocity) or twice (displacement),
 *           preserving intermediate Single stores.
 * 007D15DD..1649: log10 Single / -180 dB.
 * 007D1652..16A2,16DC..172C,179B..17E7: sqrt(P/2)*Single(scale).
 * Never an authenticated original Delphi Win32 oracle, instrument or RX.
 *
 * Example: cc -O2 -std=gnu11 -ffp-contract=off -fno-fast-math \
 * x87_spectrum_modes_reference.c -lm -o x87_modes
 * x87_modes 4096 2 1.25 65536 --y < power_f32.bin > y_f32.bin
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <errno.h>
#if !defined(__i386__) && !defined(__x86_64__)
#error "x87 required"
#endif
#if LDBL_MANT_DIG != 64
#error "x87 extended long double required"
#endif
static float f32store(long double v) {
    float r;
    __asm__ volatile("fldt %1\n\tfstps %0":"=m"(r):"m"(v):"st");
    return r;
}
static long double x87_log10f32(float v) {
    long double r;
    __asm__ volatile("fldlg2\n\tflds %1\n\tfyl2x\n\tfstpt %0":"=m"(r):"m"(v):"st");
    return r;
}
static long double x87_sqrt(long double v) {
    long double r;
    __asm__ volatile("fldt %1\n\tfsqrt\n\tfstpt %0":"=m"(r):"m"(v):"st");
    return r;
}
static int parse_uint(const char *s, unsigned long *out) {
    char *end=NULL;
    errno=0;
    unsigned long value=strtoul(s,&end,10);
    if(errno || !s[0] || !end || *end) return 0;
    *out=value;
    return 1;
}
int main(int argc, char **argv) {
    if(argc!=6)return 2;
    unsigned long requested=0,mode_value=0,rate=0;
    if(!parse_uint(argv[1],&requested) || requested<1024 ||
       requested>262144 || (requested&(requested-1)) ||
       !parse_uint(argv[2],&mode_value) || mode_value>3 ||
       !parse_uint(argv[4],&rate) || rate<1 || rate>UINT32_MAX) return 2;
    char *last=NULL;
    errno=0;
    float range=strtof(argv[3],&last);
    if(errno || !argv[3][0] || !last || *last ||
       !isfinite(range) || range<=0) return 2;
    int emit_power=!strcmp(argv[5],"--power");
    if(!emit_power && strcmp(argv[5],"--y")) return 2;
    const unsigned n=(unsigned)requested,mode=(unsigned)mode_value;
    const size_t half=n/2;
    float *p=calloc(half,sizeof(float)), *y=calloc(half,sizeof(float));
    if(!p || !y) { free(p);free(y);return 4; }
    if(fread(p,sizeof(float),half,stdin)!=half) {free(p);free(y);return 3;}
    for(size_t j=0;j<half;j++) {
        if(!isfinite(p[j]) || p[j]<0) {free(p);free(y);return 5;}
    }
    unsigned short prior=0,cw=0x1332;
    __asm__ volatile("fnstcw %0":"=m"(prior));
    __asm__ volatile("fldcw %0"::"m"(cw));
    const float scale=f32store(((long double)1/(long double)half)*range);
    const float inverse_df=f32store((long double)n/(long double)rate);
    unsigned low=(unsigned)nearbyintl(((long double)n/rate)*0.5L);
    if(low<2)low=2;
    if(low>=half)goto bad;
    for(unsigned j=0;j<low;j++)p[j]=0.f;
    if(mode>=2) {
        for(unsigned pass=0;pass<mode-1;pass++) {
            for(size_t k=1;k<half;k++) {
                const long double t=(159.154943091895L/k)*(long double)inverse_df;
                const long double v=(t*t)*(long double)p[k];
                if(!isfinite(v) || v>FLT_MAX || v<0)goto bad;
                p[k]=f32store(v);
            }
        }
    }
    const float offset=f32store(2.L*x87_log10f32((float)half));
    for(size_t k=0;k<half;k++) {
        if(mode==0) {
            y[k]=p[k]>0?f32store(
                (x87_log10f32(p[k])-(long double)offset)*10.L):-180.f;
        } else {
            const long double v=x87_sqrt((long double)p[k]/2.L)*scale;
            if(!isfinite(v) || v>FLT_MAX || v<0)goto bad;
            y[k]=f32store(v);
        }
        if(!isfinite(y[k]))goto bad;
    }
    __asm__ volatile("fnclex\n\tfldcw %0"::"m"(prior));
    if(fwrite(emit_power?p:y,sizeof(float),half,stdout)!=half) {
        free(p);free(y);return 6;
    }
    free(p);free(y);return 0;
bad:
    __asm__ volatile("fnclex\n\tfldcw %0"::"m"(prior));
    free(p);free(y);return 5;
}
